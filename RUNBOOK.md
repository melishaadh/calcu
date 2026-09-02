# RUNBOOK.md — Manual DevOps Guide ("What You Should Do")

Every exact command and every by-hand step to build, test, run, and operate
`calcu` — locally and on a fresh **AWS EC2** instance.

Legend: 🖐️ = a human must do this by hand (web console / decision).
💻 = run this command exactly.

- [Part A — Things only a human can do](#part-a--things-only-a-human-can-do)
- [Part B — Run it locally from scratch](#part-b--run-it-locally-from-scratch)
- [Part C — Deploy on AWS EC2 from scratch](#part-c--deploy-on-aws-ec2-from-scratch)
- [Part D — Secrets & environment variables](#part-d--secrets--environment-variables)
- [Part E — Day-2 operations](#part-e--day-2-operations)
- [Part F — Teardown](#part-f--teardown)

---

## Part A — Things only a human can do

These cannot be scripted from inside the repo. Do them once.

### A1. Accounts 🖐️

| Account | Needed for | Notes |
|---|---|---|
| **AWS** | the EC2 instance | A free-tier account is enough (`t3.micro` / `t2.micro`). |
| **Docker Hub** | CI pushing images | Create an **access token** (Account Settings → Security → New Access Token). Never use your password. |
| **GitHub** | source + CI | The repo must be pushed here for GitHub Actions to run. |
| **Slack** (optional) | pipeline notifications | Create an **Incoming Webhook** (api.slack.com → Your Apps → Incoming Webhooks). |
| **Jenkins host** (optional) | CD | Any machine that can reach your Kubernetes cluster and has Docker + `kubectl`. |

### A2. Create the EC2 instance 🖐️

AWS Console → **EC2** → **Launch instance**:

| Field | Value |
|---|---|
| Name | `calcu` |
| AMI | **Ubuntu Server 24.04 LTS** (x86_64) |
| Instance type | `t3.small` (2 GB RAM). `t3.micro` (1 GB) works but is tight with Postgres. |
| Key pair | Create or pick one. **Download the `.pem` file** — you need it to SSH in. |
| Network | default VPC, **Auto-assign public IP = Enable** |
| Firewall (security group) | create new, name it `calcu-sg` — rules in A3 |
| Storage | 20 GiB gp3 |

Launch. Note the **Public IPv4 address** once it's running.

### A3. Security group rules 🖐️

Edit `calcu-sg` → **Inbound rules**:

| Type | Protocol | Port | Source | Why |
|---|---|---|---|---|
| SSH | TCP | 22 | **My IP** | So you can log in. Never `0.0.0.0/0`. |
| HTTP | TCP | 80 | `0.0.0.0/0` (and `::/0`) | So the public can reach the app. |

Do **not** open 5432 (Postgres), 5001/5003 (the engines), or 8081. Outbound: leave the default "all traffic" (needed to `apt` and pull images).

### A4. IAM — do you need a role? 🖐️

For this project as written (images built **on the instance** from the Git
checkout): **no IAM role is required.**

Attach an instance role later **only if** you switch to:

| You want to… | Attach a role allowing… |
|---|---|
| Pull images from **Amazon ECR** instead of Docker Hub | `AmazonEC2ContainerRegistryReadOnly` |
| Read `POSTGRES_PASSWORD` from **SSM Parameter Store** | `ssm:GetParameter` on your parameter ARN |
| Ship logs to **CloudWatch** | `CloudWatchAgentServerPolicy` |

Create via IAM → Roles → *Create role* → *AWS service: EC2* → attach policy →
then EC2 → *Actions → Security → Modify IAM role*.

### A5. (Optional) DNS 🖐️

Point an `A` record at the instance's public IP if you have a domain. TLS
(HTTPS) is out of scope here — add it later with Caddy, or an AWS Application
Load Balancer + ACM certificate in front of the instance.

---

## Part B — Run it locally from scratch

Assumes Ubuntu/Debian or WSL2. macOS: use Docker Desktop and skip B1.

### B1. Install Docker Engine + Compose 💻

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker "$USER"
newgrp docker      # or log out/in
```

Verify:

```bash
docker --version
docker compose version
docker run --rm hello-world
```

### B2. Get the code 💻

```bash
git clone <your-repo-url> calcu
cd calcu
```

### B3. Configure 💻

```bash
cp .env.example .env
# Local defaults are fine. To use a different host port:
#   sed -i 's/^HTTP_PORT=.*/HTTP_PORT=9090/' .env
```

### B4. Build & start 💻

```bash
docker compose build
docker compose up -d
docker compose ps          # wait until every service is "running"/"healthy"
```

### B5. Verify 💻

```bash
curl -fsS -X POST http://localhost:8081/api/calculate \
  -H 'Content-Type: application/json' -d '{"operation":"add","operand1":2,"operand2":3}'
# {"operand1":2.0,"operand2":3.0,"operation":"add","result":5.0}

curl -fsS http://localhost:8081/api/history

# Health of each backend (through the gateway is not exposed; check containers):
docker compose exec calculator-engine  curl -fsS http://localhost:5001/health
docker compose exec history-service    curl -fsS http://localhost:5003/health
```

Open **http://localhost:8081** in a browser.

### B6. Logs / stop 💻

```bash
docker compose logs -f                    # all services, follow
docker compose logs -f history-service    # one service
docker compose down                       # stop & remove containers (keeps DB volume)
docker compose down -v                     # …and delete the database volume
```

### B7. Run the unit tests 💻

Needs Python 3.11+ (`sudo apt-get install -y python3 python3-pip python3-venv`).

```bash
cd calcu
for svc in calculator-engine history-service; do
  echo "=== $svc ==="
  ( cd "services/$svc" \
    && python3 -m venv .venv && . .venv/bin/activate \
    && pip install -q -r requirements.txt pytest \
    && pytest -v \
    && deactivate )
done
```

`history-service` tests use an in-memory SQLite database — no Postgres needed.

---

## Part C — Deploy on AWS EC2 from scratch

Do [Part A](#part-a--things-only-a-human-can-do) first (instance + security group exist).

### C1. Connect to the instance 💻

```bash
chmod 400 ~/Downloads/calcu-key.pem      # your .pem, once
ssh -i ~/Downloads/calcu-key.pem ubuntu@<EC2_PUBLIC_IP>
```

Everything below runs **on the instance**.

### C2. Provision the instance (once) 💻

```bash
sudo apt-get update && sudo apt-get install -y git
sudo mkdir -p /opt/calcu && sudo chown "$USER:$USER" /opt/calcu
git clone <your-repo-url> /opt/calcu
cd /opt/calcu
chmod +x deploy/*.sh
./deploy/ec2-provision.sh
```

`ec2-provision.sh` installs Docker + Compose, adds you to the `docker` group,
and enables the `ufw` host firewall (SSH + 80).

> Note: you now have **two** firewalls — the AWS security group *and* `ufw`. If
> you ever expose another port, open it in **both** (`sudo ufw allow <port>/tcp`
> and the security group). To rely on the security group alone:
> `sudo ufw disable`.

When it finishes:

```bash
newgrp docker         # apply docker group now (or log out and back in)
docker compose version
```

### C3. Configure for production 💻

```bash
cd /opt/calcu
cp .env.example .env
nano .env
```

Set at least:

```ini
HTTP_PORT=80
POSTGRES_PASSWORD=<paste output of: openssl rand -base64 24>
```

Generate the password without a text editor if you prefer:

```bash
PW=$(openssl rand -base64 24)
sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${PW}|" .env
sed -i "s|^HTTP_PORT=.*|HTTP_PORT=80|" .env
grep -E '^(HTTP_PORT|POSTGRES_PASSWORD)=' .env
```

### C4. Deploy 💻

```bash
cd /opt/calcu
ENV=prod ./deploy/deploy.sh
```

This runs `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`.
First run takes a few minutes (building 5 images).

### C5. Verify 💻

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
curl -fsS -X POST http://localhost/api/calculate \
  -H 'Content-Type: application/json' -d '{"operation":"multiply","operand1":6,"operand2":7}'
curl -fsS http://localhost/api/history
```

From your **laptop**:

```bash
curl -fsS http://<EC2_PUBLIC_IP>/api/history
```

Then open `http://<EC2_PUBLIC_IP>` in a browser.

### C6. Make it start on boot (systemd) 💻

```bash
sudo cp /opt/calcu/deploy/calcu.service /etc/systemd/system/calcu.service
sudo systemctl daemon-reload
sudo systemctl enable --now calcu.service
sudo systemctl status calcu --no-pager
```

Now the stack comes back automatically after `sudo reboot`. Manage it with:

```bash
sudo systemctl restart calcu
sudo systemctl stop calcu
journalctl -u calcu -f
```

> If you use systemd, let it own the lifecycle — don't also run
> `./deploy/deploy.sh` by hand. To ship an update, see [E2](#e2-ship-a-new-version-ec2).

---

## Part D — Secrets & environment variables

### D1. Local / EC2 — the `.env` file 💻

- Lives at the repo root, **gitignored**, never committed.
- Created from `.env.example`. Compose loads it automatically.
- Contains: `HTTP_PORT`, `POSTGRES_USER/PASSWORD/DB`, pool sizing, `IMAGE_TAG`.
- To rotate the DB password: edit `.env`, then
  `docker compose down && docker compose ... up -d`. Note: changing
  `POSTGRES_PASSWORD` after the volume exists does **not** change the password
  inside an already-initialised database — see [E4](#e4-rotate-the-database-password).

### D2. GitHub Actions secrets 🖐️

Repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Name | Value |
|---|---|
| `DOCKERHUB_USERNAME` | your Docker Hub username |
| `DOCKERHUB_TOKEN` | the Docker Hub access token from A1 |
| `SLACK_WEBHOOK_URL` | your Slack incoming-webhook URL |

The workflow reads them as `${{ secrets.NAME }}`. Nothing else to do.

### D3. Jenkins credentials 🖐️

**Manage Jenkins → Credentials → System → Global credentials → Add Credentials**:

| Kind | ID (must match exactly) | Value |
|---|---|---|
| Secret file | `kubeconfig-calcu` | your cluster's kubeconfig (`~/.kube/config`) |
| Secret text | `slack-webhook-url` | your Slack incoming-webhook URL |

Then edit `Jenkinsfile` → `DOCKERHUB_USERNAME = '<your-dockerhub-username>'`.

Jenkins agent also needs `kubectl` and `docker` on its `PATH`:

```bash
# on the Jenkins agent
sudo snap install kubectl --classic       # or the apt method
kubectl version --client
```

### D4. (Optional) pull secrets from AWS instead of `.env` 🖐️💻

Store the password in SSM Parameter Store, attach the IAM policy from A4, then
on the instance:

```bash
sudo apt-get install -y awscli
PW=$(aws ssm get-parameter --name /calcu/postgres_password --with-decryption \
      --query Parameter.Value --output text --region <your-region>)
sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${PW}|" /opt/calcu/.env
```

---

## Part E — Day-2 operations

### E1. Inspect a running stack 💻

```bash
cd /opt/calcu
CF="-f docker-compose.yml -f docker-compose.prod.yml"    # drop for local

docker compose $CF ps                       # container status + health
docker compose $CF logs -f --tail=100       # follow logs
docker compose $CF logs history-service     # one service
docker stats --no-stream                    # live CPU/RAM per container
docker compose $CF exec postgres psql -U calcu_user -d calcu_db -c '\dt'
```

### E2. Ship a new version (EC2)

**If NOT using systemd:**

```bash
cd /opt/calcu
git pull
ENV=prod ./deploy/deploy.sh
```

**If using systemd** (the unit rebuilds on start):

```bash
cd /opt/calcu
git pull
sudo systemctl restart calcu
journalctl -u calcu -f
```

### E3. Roll back (Compose)

Compose has no built-in rollback. Pin to a previous commit:

```bash
cd /opt/calcu
git log --oneline -n 5
git checkout <previous-good-sha>
ENV=prod ./deploy/deploy.sh      # or: sudo systemctl restart calcu
```

(The Kubernetes path *does* auto-roll-back — see `Jenkinsfile` `post { failure }`.)

### E4. Rotate the database password

The password is baked into the Postgres data directory on first init. To change
it on a live system:

```bash
cd /opt/calcu
CF="-f docker-compose.yml -f docker-compose.prod.yml"
NEW=$(openssl rand -base64 24)

# 1. change it inside the running database
docker compose $CF exec postgres \
  psql -U calcu_user -d calcu_db -c "ALTER USER calcu_user WITH PASSWORD '${NEW}';"

# 2. update .env so the app uses the new one
sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${NEW}|" .env

# 3. recreate the app containers (NOT postgres) to pick it up
docker compose $CF up -d --no-deps --force-recreate history-service
```

### E5. Back up / restore the history database 💻

```bash
cd /opt/calcu
CF="-f docker-compose.yml -f docker-compose.prod.yml"

# Backup
docker compose $CF exec -T postgres \
  pg_dump -U calcu_user -d calcu_db | gzip > "calcu-$(date +%F).sql.gz"

# Restore (into an empty DB)
gunzip -c calcu-2026-01-01.sql.gz | \
  docker compose $CF exec -T postgres psql -U calcu_user -d calcu_db
```

Consider a cron entry: `0 3 * * *  cd /opt/calcu && docker compose ... pg_dump ...`.

### E6. Free up disk 💻

```bash
docker image prune -f            # dangling images
docker system df                 # what's using space
docker system prune -a --volumes # AGGRESSIVE: removes unused images+volumes — check first
```

### E7. Health & troubleshooting

| Symptom | Command | Likely cause / fix |
|---|---|---|
| Site won't load from laptop | `curl -v http://<IP>/` | Security group missing port 80; or `HTTP_PORT` not 80 in `.env` |
| `history-service` unhealthy | `docker compose $CF logs history-service` | Postgres still starting — it retries ~30s; if persistent, check `DATABASE_URL` and the `postgres` container |
| "Expected JSON but got text/html" in UI | — | You hit the wrong port — use the gateway (`:80` prod, `:8081` local), not a backend |
| Postgres won't start, "directory not empty" | `docker compose $CF logs postgres` | Corrupted volume — `docker volume rm calcu-postgres-data` (destroys data) |
| Out of memory on `t3.micro` | `free -m`, `docker stats` | Add swap: `sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile && echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab` |
| Need a shell in a container | `docker compose $CF exec <service> sh` | — |

---

## Part F — Teardown

### F1. Stop the app, keep data 💻

```bash
cd /opt/calcu
sudo systemctl disable --now calcu 2>/dev/null || true
docker compose -f docker-compose.yml -f docker-compose.prod.yml down
```

### F2. Remove everything on the instance 💻

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml down -v --rmi local
docker system prune -af --volumes
sudo rm -rf /opt/calcu
sudo rm -f /etc/systemd/system/calcu.service && sudo systemctl daemon-reload
```

### F3. Delete AWS resources 🖐️

EC2 Console → Instances → select `calcu` → **Instance state → Terminate**.
Then delete the `calcu-sg` security group, the key pair (optional), and any
IAM role you created. Terminating the instance also deletes its EBS volume
(unless you unchecked "delete on termination").

---

## Appendix — one-page cheat sheet

```bash
# ---------- LOCAL ----------
cp .env.example .env
docker compose up -d --build
docker compose ps
# http://localhost:8081
docker compose logs -f
docker compose down [-v]

# ---------- EC2 (first time) ----------
ssh -i key.pem ubuntu@<IP>
sudo mkdir -p /opt/calcu && sudo chown $USER /opt/calcu
git clone <repo> /opt/calcu && cd /opt/calcu
chmod +x deploy/*.sh && ./deploy/ec2-provision.sh && newgrp docker
cp .env.example .env   # set HTTP_PORT=80 + POSTGRES_PASSWORD
ENV=prod ./deploy/deploy.sh
sudo cp deploy/calcu.service /etc/systemd/system/ && sudo systemctl enable --now calcu

# ---------- EC2 (update) ----------
cd /opt/calcu && git pull && sudo systemctl restart calcu

# ---------- TESTS ----------
cd services/<svc> && python3 -m venv .venv && . .venv/bin/activate \
  && pip install -r requirements.txt pytest && pytest -v
```
