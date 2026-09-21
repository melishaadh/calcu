A simple calculator application built to practice a complete DevOps workflow using **Docker, Docker Compose, Kubernetes, Terraform, GitHub Actions, and AWS**.

The application sends calculations from the frontend to a FastAPI backend, stores results in PostgreSQL, and returns the result to the user.

## Architecture

    GitHub
       |
       v
    GitHub Actions
       |
      OIDC
       |
       v
    Amazon ECR
       |
       v
      EC2
     /  \
    v    v
Frontend Backend
           |
           v
      RDS PostgreSQL

Terraform
    |
    +-- VPC
    +-- EC2
    +-- RDS
    +-- ECR
    +-- IAM
    +-- S3

## Technologies

| Technology | Purpose |
|---|---|
| HTML/CSS/JavaScript | Frontend |
| FastAPI / Python | Backend API |
| PostgreSQL | Database |
| Docker | Containerization |
| Docker Compose | Local development |
| Kubernetes | Container orchestration |
| Terraform | Infrastructure as Code |
| AWS EC2 | Application hosting |
| AWS RDS | Managed PostgreSQL |
| Amazon ECR | Docker image registry |
| GitHub Actions | CI and image delivery |
| AWS IAM / OIDC | Secure authentication |
| Bash | Deployment automation |

## Project Structure

    frontend/       Frontend application
    backend/        FastAPI backend
    database/       PostgreSQL initialization
    kubernetes/     Kubernetes manifests
    scripts/        Build and deployment scripts
    terraform/      AWS infrastructure
    .github/        GitHub Actions workflow

## Run Locally

### Docker Compose

    cp .env.example .env
    docker compose up --build

Access:

    Frontend: http://localhost:3000
    Backend:  http://localhost:8000/health

Stop the application:

    docker compose down

Remove the database volume:

    docker compose down -v

## Docker

Build the application images:

    ./scripts/docker-build.sh

Images:

    backend:latest
    frontend:latest

## Kubernetes

Build the Docker images:

    ./scripts/docker-build.sh

Deploy the application:

    ./scripts/kubernetes-deploy.sh

Check deployments:

    kubectl get deployments

Check pods:

    kubectl get pods

Check services:

    kubectl get services

Access:

    Frontend: http://localhost:30300
    Backend:  http://localhost:30800/health

Delete Kubernetes resources:

    ./scripts/kubernetes-delete.sh

Kubernetes resources include:

- Deployments
- Services
- ConfigMaps
- Secrets
- PersistentVolumeClaim
- Multiple application replicas

## Terraform & AWS

Terraform provisions:

- VPC and networking
- Public/private subnets
- Security Groups
- EC2
- RDS PostgreSQL
- ECR repositories
- IAM roles
- S3 bucket

Initialize Terraform:

    cd terraform
    terraform init

Validate the configuration:

    terraform validate

Create a plan:

    terraform plan

Apply the infrastructure:

    terraform apply \
      -var="db_password=YOUR_PASSWORD" \
      -var="key_name=YOUR_EC2_KEY_PAIR"

View outputs:

    terraform output

Destroy infrastructure:

    terraform destroy

## CI/CD

GitHub Actions runs when changes are pushed to `main`.

    Git Push
       |
       v
    GitHub Actions
       |
       v
    OIDC Authentication
       |
       v
    AWS IAM
       |
       v
    Docker Build
       |
       v
    Amazon ECR

The workflow builds and pushes:

    calculator-backend:latest
    calculator-backend:<commit-sha>

    calculator-frontend:latest
    calculator-frontend:<commit-sha>

GitHub OIDC is used instead of storing long-lived AWS access keys.

EC2 deployment is performed using:

    ./scripts/aws-deploy.sh

## Database

PostgreSQL stores calculation history in the `calculations` table.

    id
    operation
    a
    b
    result
    created_at

Storage by environment:

    Docker Compose → Docker Volume
    Kubernetes     → PersistentVolumeClaim
    AWS            → RDS PostgreSQL

## DevOps Concepts Demonstrated

- Git & GitHub
- Docker & Docker Compose
- Kubernetes
- Infrastructure as Code with Terraform
- CI with GitHub Actions
- Docker image delivery with Amazon ECR
- AWS cloud deployment
- GitHub OIDC and IAM
- VPC and cloud networking
- Security Groups
- Secrets and configuration management
- Bash automation
- Persistent storage
- Container scaling
- Health checks
- Deployment troubleshooting

## DevOps Workflow

    Development
         |
         v
       GitHub
         |
         v
    GitHub Actions
         |
         v
     Docker Build
         |
         v
     Amazon ECR
         |
         v
        EC2
         |
         v
    FastAPI Backend
         |
         v
    RDS PostgreSQL

**Project Goal:** Demonstrate how a simple application can be developed locally, containerized, orchestrated with Kubernetes, provisioned with Terraform, and deployed to AWS using DevOps practices.
