# Calculator App — DevOps Learning Project

A very simple calculator app built to practice a full DevOps pipeline: Docker,
Kubernetes, Terraform, GitHub Actions, and AWS.

## Architecture

```
Frontend (HTML/CSS/JS) → Backend (FastAPI) → PostgreSQL
```

Every calculation is sent to the backend, saved in Postgres, and the result is
returned to the frontend.

Production architecture on AWS:

```
Route 53 → EC2 (Frontend + Backend containers) → RDS PostgreSQL
                     ↑
              GitHub Actions → ECR
              Terraform → provisions everything
```

## Project structure

```
frontend/     static HTML/CSS/JS calculator UI
backend/      FastAPI REST API (POST /calculate, GET /health)
database/     Postgres init.sql (creates the calculations table)
kubernetes/   Deployment/Service/Secret/ConfigMap/PVC manifests
scripts/      bash scripts for build/deploy
terraform/    AWS infrastructure (EC2, ECR, IAM, RDS, S3, Route 53)
.github/      GitHub Actions CI/CD pipeline
```

## Run locally with Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend: http://localhost:8000/health
- Postgres: localhost:5432

Stop everything:

```bash
docker compose down
```

Stop and wipe the database volume:

```bash
docker compose down -v
```

## Bash scripts

```bash
scripts/docker-build.sh        # builds backend:latest and frontend:latest images
scripts/kubernetes-deploy.sh   # applies all kubernetes/ manifests
scripts/kubernetes-delete.sh   # removes everything from the cluster
scripts/aws-deploy.sh          # run on the EC2 instance: pulls from ECR, starts containers
```

Make them executable once:

```bash
chmod +x scripts/*.sh
```

## Kubernetes

Requires a running cluster (Docker Desktop, minikube, kind, etc.) and `kubectl`
configured, plus the images built locally (`scripts/docker-build.sh`) so the
cluster can use `backend:latest` / `frontend:latest`.

```bash
./scripts/kubernetes-deploy.sh
```

- Frontend: http://localhost:30300
- Backend: http://localhost:30800/health

Remove everything:

```bash
./scripts/kubernetes-delete.sh
```

Resources created: `app-config` and `postgres-init` ConfigMaps, `app-secret`
Secret, `postgres-pvc` PVC, and `postgres` / `backend` / `frontend`
Deployments + Services.

## GitHub Actions (CI/CD)

`.github/workflows/ci-cd.yml` runs on every push to `main`:

1. Logs in to AWS using GitHub Secrets (no credentials in the workflow file).
2. Builds `backend` and `frontend` Docker images.
3. Pushes them to ECR as `calculator-backend` and `calculator-frontend`,
   tagged with both `latest` and the Git commit SHA.

Required GitHub Secrets:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

## Terraform (AWS infrastructure)

Provisions: ECR repositories, an IAM role letting EC2 pull from ECR, a
security group + EC2 instance (with Docker pre-installed via user data), an
RDS PostgreSQL instance, an S3 bucket, and a Route 53 DNS record.

```bash
cd terraform
terraform init
terraform apply \
  -var="db_password=YOUR_STRONG_PASSWORD" \
  -var="key_name=YOUR_EC2_KEY_PAIR_NAME" \
  -var="domain_name=YOUR_DOMAIN_NAME"
```

`domain_name` must already have a Route 53 hosted zone in your AWS account.
`key_name` must be an existing EC2 key pair (used for SSH access).

Outputs include the ECR repository URLs, the EC2 public IP, the RDS
endpoint, the S3 bucket name, and the final domain.

Tear down:

```bash
terraform destroy
```

## Deploying to EC2 (ECR → EC2 → RDS)

1. `terraform apply` to create the infrastructure.
2. Push images to ECR (either via GitHub Actions, or manually with
   `scripts/docker-build.sh` + `docker push`).
3. SSH into the EC2 instance (`terraform output ec2_public_ip`).
4. Export the required variables and run the deploy script:

```bash
export AWS_ACCOUNT_ID=<your account id>
export AWS_REGION=us-east-1
export RDS_ENDPOINT=<terraform output rds_endpoint>
export POSTGRES_DB=calculator
export POSTGRES_USER=calculator
export POSTGRES_PASSWORD=<your db password>
./scripts/aws-deploy.sh
```

5. Visit `http://<ec2_public_ip>` (or your Route 53 domain).

## Troubleshooting

- **Backend can't connect to Postgres**: the backend retries on startup for
  ~30 seconds. If it still fails, check `POSTGRES_HOST`/`POSTGRES_PORT` env
  vars match the database container/service name.
- **Frontend shows "Could not reach backend"**: check `API_URL` in
  `frontend/config.js` (Docker) or the `app-config` ConfigMap (Kubernetes) —
  it must point to a backend address reachable from your browser.
- **Kubernetes pods stuck in `ImagePullBackOff`**: build the images locally
  first with `scripts/docker-build.sh` so the cluster can find
  `backend:latest` / `frontend:latest`.
- **RDS connection refused from EC2**: confirm the EC2 instance and RDS
  instance are in the same VPC and the `rds_sg` security group allows port
  5432 from the `app_sg` security group (this is set up automatically by
  Terraform).
