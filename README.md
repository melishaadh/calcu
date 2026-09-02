# calcu — Simple Calculator

A basic web calculator: add, subtract, multiply, and divide, with your last
7 days of calculations saved automatically. Under the hood it's a small set
of containerized services, so it also doubles as a DevOps demo (Docker,
Kubernetes, CI/CD) — see [`DEVOPS_GUIDE.md`](DEVOPS_GUIDE.md) and
[`RUNBOOK.md`](RUNBOOK.md) if you want the operator-level detail.

## What it does

- **Calculate**: enter two numbers, pick `+ − × ÷`, get the result.
- **History**: every calculation is saved to a PostgreSQL database and shown
  on the page. Only the last **7 days** are kept — anything older is deleted
  automatically, no manual cleanup needed.

## Architecture

```
                         ┌────────────┐
   client ───────────▶   │   Nginx    │   calcu-nginx — reverse proxy / gateway
                         └─────┬──────┘
              ┌────────────────┼────────────────┐
              ▼                ▼                 ▼
        ┌──────────┐   ┌──────────────┐   ┌──────────────┐
        │ frontend │   │  calculator  │   │   history    │
        │ (static) │   │   engine     │   │   service    │
        └──────────┘   └──────┬───────┘   └──────┬───────┘
                              └──────────────────┴─────────────────┐
                                                 │  POST /api/history
                                                 ▼
                                         ┌───────────────┐
                                         │  PostgreSQL   │
                                         └───────────────┘
```

| Component | Image | Port | Role |
|---|---|---|---|
| frontend | `calcu-frontend` | 80 | The web page (served by Nginx) |
| calculator-engine | `calcu-calculator-engine` | 5001 | `POST /api/calculate` — add, subtract, multiply, divide |
| history-service | `calcu-history-service` | 5003 | `GET/POST /api/history` — saves and reads calculations; deletes anything older than 7 days |
| nginx | `calcu-nginx` | 80 | Routes `/api/*` to the right service, everything else to the frontend |
| postgres | `postgres:16-alpine` | 5432 | Stores calculation history |

All image, container, network, and volume names use the **`calcu-`** prefix.

## Quick start (local, Docker Compose)

```bash
cd calcu
cp .env.example .env          # defaults are fine for local use
docker compose up -d --build
docker compose ps
```

Open **http://localhost:8081**.

> Port 8081 is used instead of the more common 8080 because 8080 is already
> taken by Jenkins on this machine. Change `HTTP_PORT` in `.env` if you need
> a different port.

```bash
# Try the API directly:
curl -X POST http://localhost:8081/api/calculate \
  -H 'Content-Type: application/json' \
  -d '{"operation":"add","operand1":2,"operand2":3}'

curl http://localhost:8081/api/history

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
cd services/calculator-engine && pip install -r requirements.txt pytest && pytest -v
cd ../history-service        && pip install -r requirements.txt pytest && pytest -v
```

## Deploy to local Kubernetes (Minikube / K3s / MicroK8s)

```bash
# 1. Build the images INTO the cluster's Docker daemon (Minikube shown):
eval $(minikube docker-env)
docker build -t calcu-calculator-engine:latest  services/calculator-engine
docker build -t calcu-history-service:latest    services/history-service
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

If your cluster already runs its own ingress (e.g. **Traefik** on K3s),
`k8s/ingress.yaml` is a second access path — `k8s/gateway.yaml`'s NodePort
works either way and needs no ingress controller at all.

`k8s/gateway.yaml` (a NodePort running `calcu-nginx`) works with **no**
Ingress Controller. `k8s/ingress.yaml` is a second access path once one is
enabled.

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
├── frontend/                     the web page (HTML/CSS/JS) + its Dockerfile
├── services/
│   ├── calculator-engine/        Flask + Gunicorn — /api/calculate
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
| Browser shows "Request failed: Expected JSON but got text/html" | You reached the bare `frontend` instead of the `nginx` gateway — use the gateway URL (`:8081` locally, `:30080` NodePort on k8s) |
| Port 8080 already in use | That's expected — Jenkins owns 8080 on this host. calcu listens on **8081** by default (see `.env`) |
| HPA shows `<unknown>` targets | `metrics-server` isn't enabled in the cluster |
| EC2: site doesn't load | Security group must allow inbound TCP 80; `.env` must have `HTTP_PORT=80`; check `docker compose ps` |
| Slack messages never arrive | Secret/credential names must match exactly: `SLACK_WEBHOOK_URL` (GitHub), `slack-webhook-url` (Jenkins) |
