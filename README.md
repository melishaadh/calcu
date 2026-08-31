# calcu — Distributed Scientific & Financial Calculator

An end-to-end DevOps demo: Python/Flask microservices behind an Nginx gateway,
containerised with Docker, tested and shipped by GitHub Actions + Jenkins, and
deployable three ways — **Docker Compose locally**, **Docker Compose on an AWS
EC2 instance**, or a **local Kubernetes cluster** (Minikube/K3s/MicroK8s).

📘 **New here? Read the two guides:**

| Guide | What it covers |
|---|---|
| [`DEVOPS_GUIDE.md`](DEVOPS_GUIDE.md) | Beginner-friendly walkthrough of the whole project — what every folder does, and plain-English explanations of Nginx, the CI/CD pipeline, Dockerfiles, and Compose/EC2 deployment. |
| [`RUNBOOK.md`](RUNBOOK.md) | The manual operator guide: every exact Linux command to build, test, and run the app from scratch — locally and on a brand-new EC2 instance — plus the AWS steps (instance, security group, IAM) that a human must do by hand. |

## Architecture

```
                         ┌────────────┐
   client ───────────▶   │   Nginx    │   calcu-nginx — reverse proxy / API gateway
                         └─────┬──────┘   (or the Nginx Ingress on Kubernetes)
              ┌────────────────┼────────────────┬───────────────┐
              ▼                ▼                ▼                ▼
        ┌──────────┐   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
        │ frontend │   │  scientific  │  │  financial   │  │   history    │
        │ (static) │   │   engine     │  │   engine     │  │   service    │
        └──────────┘   └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
                              └─────────────────┴─────────────────┘
                                                 │  POST /api/history
                                                 ▼
                                         ┌───────────────┐
                                         │  PostgreSQL   │
                                         └───────────────┘
```

| Component | Image | Port | Role |
|---|---|---|---|
| frontend | `calcu-frontend` | 80 | Static HTML/CSS/JS UI (served by Nginx) |
| scientific-engine | `calcu-scientific-engine` | 5001 | `POST /api/scientific` — trig, logs, roots, factorial |
| financial-engine | `calcu-financial-engine` | 5002 | `POST /api/financial` — simple/compound interest, EMI |
| history-service | `calcu-history-service` | 5003 | `GET/POST /api/history` — persists every calculation |
| nginx | `calcu-nginx` | 80 | Routes `/api/*` to the engines, everything else to the frontend |
| postgres | `postgres:16-alpine` | 5432 | Stores calculation history |

All image, container, network, and volume names use the **`calcu-`** prefix.

## Quick start (local, Docker Compose)

```bash
cd calcu
cp .env.example .env          # defaults are fine for local use
docker compose up -d --build
docker compose ps
```

Open **http://localhost:8080**.

```bash
# Try the APIs directly:
curl -X POST http://localhost:8080/api/scientific \
  -H 'Content-Type: application/json' -d '{"operation":"sqrt","value":16}'

curl -X POST http://localhost:8080/api/financial \
  -H 'Content-Type: application/json' \
  -d '{"operation":"emi","principal":100000,"annual_rate":10,"tenure_months":12}'

curl http://localhost:8080/api/history

# Tear down (add -v to also wipe the database volume):
docker compose down
```

## Deploy on AWS EC2

Full step-by-step (instance, security group, IAM, commands) is in
[`RUNBOOK.md`](RUNBOOK.md). The short version, once Docker is installed on the
instance and the repo is at `/opt/calcu`:

```bash
cd /opt/calcu
cp .env.example .env
# edit .env: set HTTP_PORT=80 and a strong POSTGRES_PASSWORD
ENV=prod ./deploy/deploy.sh
```

Then browse to `http://<EC2 public IP>`.

## Run the unit tests

```bash
cd services/scientific-engine && pip install -r requirements.txt pytest && pytest -v
cd ../financial-engine        && pip install -r requirements.txt pytest && pytest -v
cd ../history-service         && pip install -r requirements.txt pytest && pytest -v
```

## Deploy to local Kubernetes (Minikube / K3s / MicroK8s)

```bash
# 1. Build the images INTO the cluster's Docker daemon (Minikube shown):
eval $(minikube docker-env)
docker build -t calcu-history-service:latest    services/history-service
docker build -t calcu-scientific-engine:latest  services/scientific-engine
docker build -t calcu-financial-engine:latest   services/financial-engine
docker build -t calcu-frontend:latest           frontend
docker build -t calcu-nginx:latest              nginx

# 2. Enable the add-ons the manifests use:
minikube addons enable ingress          # for k8s/ingress.yaml
minikube addons enable metrics-server   # for k8s/hpa.yaml

# 3. Apply everything (namespace first):
kubectl apply -f k8s/postgres-pv-pvc-secret.yaml
kubectl apply -f k8s/deployments-and-services.yaml
kubectl apply -f k8s/gateway.yaml
kubectl apply -f k8s/hpa.yaml
kubectl apply -f k8s/ingress.yaml

# 4. Check and open:
kubectl get pods -n calcu
minikube service gateway -n calcu --url        # prints the URL to visit
```

`k8s/gateway.yaml` (a NodePort running `calcu-nginx`) works with **no** Ingress
Controller. `k8s/ingress.yaml` is a second access path once one is enabled.

## CI/CD

| Pipeline | File | Trigger | Does |
|---|---|---|---|
| CI | [`.github/workflows/ci.yml`](.github/workflows/ci.yml) | push / PR to `main` | pytest → build images → Trivy scan → push to Docker Hub (push to `main` only) → Slack |
| CD | [`Jenkinsfile`](Jenkinsfile) | manual / webhook | `kubectl set image` rolling update of every Deployment → verify rollout → Slack, auto-rollback on failure |

**Secrets you must configure yourself** (they are never committed):

*GitHub* → repo Settings → Secrets and variables → Actions:

| Secret | Value |
|---|---|
| `DOCKERHUB_USERNAME` | your Docker Hub username |
| `DOCKERHUB_TOKEN` | a Docker Hub **access token** (Account Settings → Security) |
| `SLACK_WEBHOOK_URL` | a Slack incoming-webhook URL |

*Jenkins* → Manage Jenkins → Credentials → Global:

| Kind | ID (exact) | Value |
|---|---|---|
| Secret file | `kubeconfig-calcu` | your cluster's kubeconfig file |
| Secret text | `slack-webhook-url` | your Slack incoming-webhook URL |

Also set your Docker Hub username in [`Jenkinsfile`](Jenkinsfile) (`DOCKERHUB_USERNAME`).

## Repository layout

```
calcu/
├── frontend/                     static HTML/CSS/JS UI + its Dockerfile
├── services/
│   ├── scientific-engine/        Flask + Gunicorn — /api/scientific
│   ├── financial-engine/         Flask + Gunicorn — /api/financial
│   └── history-service/          Flask + Gunicorn + SQLAlchemy — /api/history
├── db/init.sql                   Postgres schema bootstrap (Compose)
├── nginx/                        gateway config + Dockerfile (calcu-nginx)
├── deploy/                       EC2 provisioning + deployment scripts + systemd unit
├── docker-compose.yml            base stack (local + EC2)
├── docker-compose.prod.yml       EC2 overrides (port 80, log rotation, no DB port)
├── .env.example                  copy to .env
├── .github/workflows/ci.yml      GitHub Actions CI
├── Jenkinsfile                   Jenkins CD
├── k8s/                          Kubernetes manifests
├── DEVOPS_GUIDE.md               ← beginner explanation
└── RUNBOOK.md                    ← manual operator guide
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `docker compose up` fails on `history-service` | Postgres wasn't ready; the service retries for ~30s on its own — re-run `docker compose up -d` if it still shows unhealthy |
| Browser shows "Request failed: Expected JSON but got text/html" | You reached the bare `frontend` instead of the `nginx` gateway — use the gateway URL (`:8080` locally, `:30080` NodePort on k8s) |
| HPA shows `<unknown>` targets | `metrics-server` isn't enabled in the cluster |
| EC2: site doesn't load | Security group must allow inbound TCP 80; `.env` must have `HTTP_PORT=80`; check `docker compose ps` |
| Slack messages never arrive | Secret/credential names must match exactly: `SLACK_WEBHOOK_URL` (GitHub), `slack-webhook-url` (Jenkins) |
