# DEVOPS_GUIDE.md — Understanding the calcu Project

A plain-English tour of how this project is built and shipped. No prior DevOps
experience assumed. If you just want the commands, jump to
[`RUNBOOK.md`](RUNBOOK.md).

---

## 1. What the application actually is

`calcu` is a calculator that has been deliberately split into **several small
programs that talk to each other over the network**, instead of one big program.
Each small program is a **microservice**.

| Microservice | Language | What it does | Talks to |
|---|---|---|---|
| **frontend** | HTML/CSS/JS | The web page you see. Has buttons and shows results. | The browser calls the other services *through Nginx*. |
| **scientific-engine** | Python (Flask) | Does `sin`, `cos`, `log`, `sqrt`, `factorial`, … | Calls history-service to log each calculation. |
| **financial-engine** | Python (Flask) | Does simple interest, compound interest, EMI. | Calls history-service to log each calculation. |
| **history-service** | Python (Flask + SQLAlchemy) | Reads/writes the list of past calculations. | Reads/writes **PostgreSQL**. |
| **PostgreSQL** | — | The database. Stores the history rows on disk. | Nobody else — only history-service. |
| **nginx** | — | The "front door". Decides which service each request goes to. | All of the above. |

### Why split it up?

- **Independent scaling** — trig math is CPU-heavy; you can run 8 copies of
  scientific-engine and only 1 database.
- **Independent deploys** — fix a bug in the financial formulas without
  touching anything else.
- **Clear boundaries** — only history-service knows how the database works.
- **It's a teaching project** — this is the smallest realistic setup that
  exercises every common DevOps tool.

### How a single click flows through the system

```
You click "Calculate" (sqrt of 16)
  │
  ▼
Browser sends:  POST /api/scientific   {"operation":"sqrt","value":16}
  │
  ▼
NGINX sees the path starts with /api/scientific  →  forwards to scientific-engine:5001
  │
  ▼
scientific-engine computes 4.0
  │           └──▶ fires POST /api/history {"expression":"sqrt(16.0)","result":4.0,...}
  │                       │
  │                       ▼
  │                 history-service  →  INSERT INTO calculation_history ...  →  PostgreSQL
  │
  ▼
scientific-engine replies  {"operation":"sqrt","value":16.0,"result":4.0}
  │
  ▼
NGINX passes it straight back to the browser, which shows "sqrt(16) = 4.0"
```

Every few seconds the frontend also calls `GET /api/history` so the "Live
Calculation History" panel updates even when *someone else* did the maths.

---

## 2. The folder map

```
calcu/
├── frontend/                  The web UI.
│   ├── index.html             Page structure.
│   ├── style.css              Looks.
│   ├── app.js                 Behaviour — the fetch() calls to /api/*.
│   └── Dockerfile             How to package it into a container.
│
├── services/                  The three Python microservices. Same shape each:
│   ├── <service>/app.py           The Flask application (routes + logic).
│   ├── <service>/wsgi.py          Entry point Gunicorn imports in production.
│   ├── <service>/requirements.txt Python libraries to install.
│   ├── <service>/test_app.py      Unit tests (pytest).
│   ├── <service>/Dockerfile       How to package it.
│   └── <service>/.dockerignore    Files to keep OUT of the image.
│
├── db/init.sql               Creates the history table when Postgres first starts.
├── nginx/
│   ├── nginx.conf            The routing rules (which path → which service).
│   └── Dockerfile            Packages nginx.conf into the calcu-nginx image.
│
├── deploy/                   Operator tooling for servers:
│   ├── ec2-provision.sh      Installs Docker on a fresh EC2 box (run once).
│   ├── deploy.sh            Builds + starts/updates the stack.
│   └── calcu.service        systemd unit so the stack starts on boot.
│
├── docker-compose.yml       Describes all 6 containers + how they connect.
├── docker-compose.prod.yml  A thin overlay with EC2-only changes.
├── .env.example             Template for secrets/config → copy to .env.
│
├── .github/workflows/ci.yml GitHub Actions: test, build, scan, push.
├── Jenkinsfile              Jenkins: roll the new images out to Kubernetes.
└── k8s/                     Kubernetes manifests (the alternative to Compose).
```

---

## 3. Containers & Dockerfiles

### The idea

A **container** is your program plus *everything it needs to run* (the right
Python version, the right libraries, the OS bits) sealed into one bundle called
an **image**. "Works on my machine" stops being a problem because the machine
comes *with* the program.

- **Image** = the frozen bundle (a template). Built once.
- **Container** = a running copy of an image. You can start many from one image.

### A Dockerfile is the recipe for an image

Here is `services/scientific-engine/Dockerfile`, annotated:

```dockerfile
# ---- Build stage: install dependencies in a throwaway layer ----
FROM python:3.11-slim AS builder          # start from a small Python 3.11 OS
WORKDIR /app                              # work in /app inside the image
RUN python -m venv /opt/venv              # make a clean virtual environment
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .                   # copy ONLY the deps list first…
RUN pip install --no-cache-dir -r requirements.txt   # …so this layer is cached
                                                     #    unless deps change

# ---- Runtime stage: copy just what's needed to RUN ----
FROM python:3.11-slim AS runtime
RUN apt-get update && apt-get upgrade -y  # patch OS security updates
 && useradd --uid 1000 appuser            # create a non-root user
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv   # bring the installed libraries over
COPY app.py wsgi.py ./                    # bring the code
USER appuser                              # run as non-root (safer)
EXPOSE 5001                               # documents the port it listens on
HEALTHCHECK ... CMD curl .../health       # Docker keeps checking it's alive
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "2", "wsgi:app"]
```

Key techniques used across all the Dockerfiles here:

| Technique | Why |
|---|---|
| **Multi-stage build** (`builder` → `runtime`) | Compilers and build tools stay in the builder; the final image is small and has less to attack. |
| **Copy `requirements.txt` before the code** | Docker caches layers. Code changes far more often than dependencies, so this ordering means most rebuilds skip re-installing everything. |
| **`USER appuser` (non-root)** | If someone breaks into the container, they're not root. |
| **`apt-get upgrade` in the runtime stage** | Picks up OS security patches released after the base image was published. |
| **`HEALTHCHECK`** | Docker/Kubernetes can tell a *hung* container from a *healthy* one and restart it. |
| **`.dockerignore`** | Keeps `test_app.py`, `__pycache__`, `.env` out of the image — smaller and no secrets. |
| **Gunicorn, not `flask run`** | Flask's built-in server is single-threaded and explicitly "not for production". Gunicorn runs multiple worker processes. |

### The two Nginx images

`calcu-frontend` and `calcu-nginx` are **both** based on `nginx:alpine`, but:

- **`calcu-frontend`** copies the HTML/CSS/JS into `/usr/share/nginx/html` and
  just serves static files.
- **`calcu-nginx`** copies `nginx/nginx.conf` and acts as the **gateway** —
  it doesn't serve files, it *forwards* requests to other services.

---

## 4. NGINX — the reverse proxy / gateway

### What "reverse proxy" means

A normal proxy sits in front of *you* and fetches web pages on your behalf.
A **reverse proxy** sits in front of *the servers* and decides which one should
answer each incoming request. The client only ever sees one address.

### Why calcu needs it

The browser makes calls to `/api/scientific`, `/api/financial`,
`/api/history`, and also loads `/`, `/style.css`, `/app.js`. Those live on
**four different services** on four different ports. Without a gateway the
frontend JavaScript would need to know every service's address, and browsers
would block the cross-origin calls anyway.

Nginx gives everything **one origin** (`http://localhost:8080`, or your EC2
address) and routes internally.

### The routing rules (`nginx/nginx.conf`), explained

```nginx
upstream scientific_upstream { server scientific-engine:5001; }   # a friendly name
...

server {
    listen 80;                       # accept HTTP on port 80 inside the container
    client_max_body_size 1m;         # reject uploads bigger than 1 MB

    # If a backend is down or a path is wrong, return JSON — not Nginx's HTML
    # error page — so the frontend's JSON.parse() never chokes.
    error_page 404 = @json_404;
    error_page 500 502 503 504 = @json_5xx;

    location /api/scientific {                       # path starts with this →
        proxy_pass http://scientific_upstream/api/scientific;   # send to that service
        proxy_set_header X-Real-IP $remote_addr;     # tell the backend who called
    }
    location /api/financial { proxy_pass http://financial_upstream/api/financial; }
    location /api/history   { proxy_pass http://history_upstream/api/history; }

    location / {                                     # everything else →
        proxy_pass http://frontend_upstream/;        # the static frontend
    }
}
```

`scientific-engine`, `financial-engine`, etc. are **DNS names** that Docker
Compose (and Kubernetes) create automatically — every service can reach every
other by its name on the private network.

### On Kubernetes

Same job, two options:
- **`k8s/gateway.yaml`** runs the *identical* `calcu-nginx` image as a pod.
- **`k8s/ingress.yaml`** hands the routing to the cluster's shared "Nginx
  Ingress Controller" instead of running our own.

---

## 5. The CI/CD pipeline

**CI (Continuous Integration)** = every code change is automatically tested and
built. **CD (Continuous Deployment/Delivery)** = those built artifacts are
automatically rolled out.

This project splits them across two tools on purpose (both are common in
industry, so the demo shows both):

```
 ┌─────────────────────── GitHub Actions (CI) ────────────────────────┐
 │  git push  →  TEST  →  BUILD images  →  SCAN (Trivy)  →  PUSH to    │
 │              (pytest)   (docker build)   (vuln check)    Docker Hub │
 └───────────────────────────────┬───────────────────────────────────-┘
                                 │  images now exist at
                                 │  docker.io/<you>/calcu-<service>:<git-sha>
                                 ▼
 ┌─────────────────────────── Jenkins (CD) ───────────────────────────┐
 │  trigger  →  connect to Kubernetes  →  kubectl set image (rolling) │
 │             →  wait for healthy rollout  →  Slack ✅  (or rollback) │
 └───────────────────────────────────────────────────────────────────-┘
                    (Slack message at the end of each)
```

### CI stages — `.github/workflows/ci.yml`

| Stage | Job name | What happens | Fails the build if… |
|---|---|---|---|
| **Test** | `test` | Spins up 3 parallel runners (one per Python service), installs deps, runs `pytest -v`. | any test fails |
| **Build** | `build-scan-push` | `docker build` for all 5 images (3 services + frontend + nginx), each tagged with the **git commit SHA** and `latest`. | a Dockerfile is broken |
| **Scan** | (same job) | Runs **Trivy** against each freshly built image, printing CRITICAL/HIGH OS+library vulnerabilities. Currently **non-blocking** (`--exit-code 0`) — it reports but doesn't stop the pipeline, because base-image CVEs are outside our control. | never (by design; flip to `--exit-code 1` for a hard gate) |
| **Push** | (same job) | `docker push` both tags to Docker Hub. **Only on a real push to `main`**, never on a pull request. | Docker Hub rejects the push |
| **Notify** | `notify` | One Slack message: ✅ SUCCESS or ❌ FAILURE, with repo/branch/commit/author. Runs even if earlier stages failed. | never |

**Why tag with the git SHA?** So Jenkins can later deploy *one exact,
known-good build* — not a moving `latest` that might have changed underneath it.

**About Trivy and the pinned version.** Trivy is a free vulnerability scanner.
In March 2026 the `aquasecurity/trivy-action` Marketplace action *and* some
Trivy releases were briefly compromised in a supply-chain attack. This workflow
therefore runs Trivy from its **official container image at a fixed pre-incident
tag** (`aquasec/trivy:0.55.2`) rather than the Marketplace action — a small,
deliberate example of supply-chain hardening.

### CD stages — `Jenkinsfile`

| Stage | What happens |
|---|---|
| **Checkout Code** | Pull the repo; work out which image tag to deploy (build parameter, or the triggering commit SHA, or `latest`). |
| **Notify: Start** | Post ":rocket: Deployment STARTED" to Slack. |
| **Connect to Kubernetes** | Load the kubeconfig from Jenkins' credential store; `kubectl get nodes` to prove the connection. |
| **Deploy: Rolling Update** | For each service: `kubectl set image deployment/<svc> <svc>=<you>/calcu-<svc>:<tag>`. Kubernetes then starts new pods and retires old ones **one at a time** — no downtime. |
| **Verify Rollout Health** | `kubectl rollout status …` waits until every new pod passes its readiness probe. If one doesn't within 180s → the stage errors. |
| **post { success }** | Slack ✅. |
| **post { failure }** | Slack ❌, then `kubectl rollout undo` on every deployment (automatic rollback), then Slack "rollback completed". |

### Why secrets are never in these files

`ci.yml` and `Jenkinsfile` live in Git. Anyone who can read the repo could read
a hard-coded password or webhook URL. So both files only *reference* secrets by
name (`${{ secrets.DOCKERHUB_TOKEN }}`, `credentials('slack-webhook-url')`) and
you paste the real values into GitHub's and Jenkins' own encrypted stores. See
[`RUNBOOK.md`](RUNBOOK.md) §7.

---

## 6. Docker Compose — one file, the whole stack

`docker-compose.yml` is a single description of all six containers: what image
each uses, what environment variables it gets, which depends on which, and what
network they share.

### The important parts

```yaml
name: calcu                       # prefixes the project's resources

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-calcu_pass}   # from .env, default calcu_pass
    volumes:
      - calcu-postgres-data:/var/lib/postgresql/data        # data survives restarts
      - ./db/init.sql:/docker-entrypoint-initdb.d/init.sql:ro   # runs on first start
    healthcheck:                                            # "is Postgres accepting connections?"
      test: ["CMD-SHELL", "pg_isready -U ... -d ..."]

  history-service:
    build: { context: ./services/history-service }         # build from that Dockerfile
    image: calcu-history-service:${IMAGE_TAG:-latest}       # …and name the result this
    environment:
      DATABASE_URL: postgresql+psycopg2://.../calcu_db      # how to reach Postgres
    depends_on:
      postgres: { condition: service_healthy }              # wait for the healthcheck

  nginx:
    build: { context: ./nginx }
    ports:
      - "${HTTP_PORT:-8080}:80"      # host:container — the ONLY port exposed to you

networks:
  calcu-net: { driver: bridge }     # private network; service names resolve on it

volumes:
  calcu-postgres-data:              # named volume = the database's disk
```

Concepts:

| Term | Meaning |
|---|---|
| **service** | One container definition. |
| **`build` vs `image`** | `build` says *how* to make the image; `image` *names* it. Having both means `docker compose build` produces a predictably-named image. |
| **`depends_on` + `condition: service_healthy`** | Start ordering. history-service won't start until Postgres passes its healthcheck. |
| **volume** | Disk storage that outlives the container. Without it, `docker compose down` would delete all history. |
| **network** | The private LAN. `history-service` can `ping postgres` because they share `calcu-net`. |
| **`${VAR:-default}`** | Read `VAR` from `.env`; use `default` if unset. This is what makes the *same file* work locally and on EC2. |
| **`expose` vs `ports`** | `expose` = reachable by other containers only. `ports` = published to the host machine. Only Nginx (and, bound to localhost, Postgres) publish ports. |

### The production overlay — `docker-compose.prod.yml`

Compose can merge multiple files. `docker compose -f docker-compose.yml -f
docker-compose.prod.yml up` applies the base file, then the overlay on top.
The overlay only changes what's different on a server:

- `restart: always` — bring containers back after an EC2 reboot.
- `logging:` limits — cap each container's log files at 3 × 10 MB so a small
  instance disk never fills.
- `ports: !reset []` on Postgres — publish **nothing**; the database is only
  reachable on the private network.

`HTTP_PORT=80` in `.env` is what makes the site answer on the normal web port.

---

## 7. EC2 deployment — how the pieces fit

```
        Internet
           │  HTTP :80
           ▼
   ┌──────────────────────────────────────────────┐
   │  AWS EC2 instance (Ubuntu)                    │
   │                                              │
   │  Security Group  ── allows :22 (you), :80    │
   │                                              │
   │  Docker Engine                               │
   │   └─ docker compose project "calcu"          │
   │        calcu-nginx  :80 ─┬─ calcu-frontend   │
   │                          ├─ calcu-scientific │
   │                          ├─ calcu-financial  │
   │                          └─ calcu-history ─ calcu-postgres (private, volume-backed)
   │                                              │
   │  systemd unit "calcu.service" → starts it on boot
   └──────────────────────────────────────────────┘
```

There is **no AWS-specific code** in the app. EC2 is just "a Linux box with a
public IP". The only AWS things a human configures are the instance itself, its
**security group** (a cloud firewall — you must open port 80), and optionally an
**IAM role** if you later want the instance to pull private images from ECR or
read secrets from Parameter Store. All of that is spelled out in
[`RUNBOOK.md`](RUNBOOK.md).

What each `deploy/` file does:

| File | Run it… | Purpose |
|---|---|---|
| `deploy/ec2-provision.sh` | once, on a fresh instance | Installs Docker + Compose from Docker's official apt repo, adds you to the `docker` group, turns on the host firewall (`ufw`). |
| `deploy/deploy.sh` | every deploy | `git pull` → `docker compose build` → `up -d`. `ENV=prod` adds the overlay. Idempotent — safe to run repeatedly. |
| `deploy/calcu.service` | install once | systemd unit; `systemctl enable` it so the stack starts automatically after a reboot. |

---

## 8. Kubernetes — the same app, orchestrated

Compose runs containers on **one** machine. Kubernetes runs them across a
**cluster** and adds self-healing, autoscaling, and rolling updates as
first-class features. This repo targets **local** clusters (Minikube / K3s /
MicroK8s) — no cloud Kubernetes.

| Manifest | Kubernetes objects | Compose equivalent |
|---|---|---|
| `postgres-pv-pvc-secret.yaml` | `Namespace`, `Secret`, `PersistentVolumeClaim`, `StatefulSet`, headless `Service` | the `postgres` service + its volume + env |
| `deployments-and-services.yaml` | 4 × (`Deployment` + `Service`) | the 4 app services |
| `gateway.yaml` | `Deployment` + NodePort `Service` running `calcu-nginx` | the `nginx` service + its published port |
| `ingress.yaml` | `Ingress` | an alternative to `gateway.yaml`, using the cluster's shared ingress controller |
| `hpa.yaml` | 2 × `HorizontalPodAutoscaler` | *(no equivalent — Compose can't autoscale)* |

Concepts worth knowing:

- **Deployment** — "keep N copies of this pod running; replace any that die;
  roll updates out gradually."
- **Service** — a stable internal name + IP for a changing set of pods.
- **StatefulSet** — like a Deployment but for things with identity and storage
  (databases). Postgres uses one.
- **Secret** — base64-wrapped config (⚠️ *not* encrypted at rest by default).
- **PersistentVolumeClaim** — "I need 5 GB of disk"; the cluster provides it.
- **HorizontalPodAutoscaler** — watches CPU/memory and changes the replica
  count automatically (needs `metrics-server`).
- **readiness probe** — "can this pod take traffic yet?" Controls rolling
  updates. **liveness probe** — "is it wedged and in need of a restart?"

---

## 9. Where the bodies are buried (recent fixes)

If you're comparing against an older checkout, these are the correctness fixes
that were made during the cleanup:

| Area | Was | Now |
|---|---|---|
| **history-service schema** | Table only created by `db/init.sql`, so on Kubernetes (no init hook) the first write failed with *relation "calculation_history" does not exist*. | `init_db()` runs SQLAlchemy `create_all()` on startup, with a bounded retry while Postgres wakes up. Works in every environment. |
| **DB connection pool** | Fixed `pool_size=5, max_overflow=10` per worker — could exhaust Postgres' 100-connection limit across replicas. | Configurable via `DB_POOL_SIZE` / `DB_MAX_OVERFLOW`; smaller, documented defaults; `pool_recycle` added. |
| **scientific-engine overflow** | `math.exp(1000)` / huge `pow` raised `OverflowError`, which fell through to a generic HTTP 500. | Caught → HTTP 400 with a clear message. `factorial` input validated and capped at 170. |
| **CI / Trivy** | Used `aquasecurity/trivy-action@v0.36.0` (a Marketplace action from a family compromised in March 2026). Slack payload built by string-interpolating the commit message → a message with a `"` broke the JSON. | Trivy runs from the pinned official image `aquasec/trivy:0.55.2`; Slack payload built with `jq` (injection-safe); workflow given least-privilege `permissions:` and `concurrency:`. |
| **k8s ingress** | (verified) `namespace: calcu` present and correct. | unchanged |
| **Naming** | Mixed: `history-service:latest` in k8s, `calcu-history-service` in CI. `gateway.yaml` carried a byte-for-byte copy of `nginx.conf` in a ConfigMap. | Everything is `calcu-<service>`. `gateway.yaml` runs the real `calcu-nginx` image — one source of truth for the routing config. |
| **Compose** | Postgres published on `0.0.0.0:5432`; credentials hard-coded. | Bound to `127.0.0.1` (and nothing at all in prod); credentials from `.env`. |

---

Next: [`RUNBOOK.md`](RUNBOOK.md) for the exact commands.
