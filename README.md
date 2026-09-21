# Calculator App — DevOps Learning Project

A simple calculator application built to practice a complete DevOps workflow using Docker, Docker Compose, Kubernetes, Terraform, GitHub Actions, and AWS.

Every calculation is sent from the frontend to the backend, processed by the FastAPI API, stored in PostgreSQL, and the result is returned to the frontend.

## Architecture

### Application Architecture

```text
Frontend (HTML/CSS/JS)
          |
          v
Backend (FastAPI)
          |
          v
PostgreSQL
User enters calculation
          |
          v
Frontend
          |
          v
FastAPI Backend
          |
          v
PostgreSQL
          |
          v
Result returned to Frontend

**Production Architecture on AWS**

                    AWS
                     |
              +------+------+
              |             |
             EC2           RDS
              |          PostgreSQL
        +-----+-----+
        |           |
    Frontend     Backend
    Container    Container
                     ^
                     |
                  Amazon ECR
                     ^
                     |
              GitHub Actions
                     |
                GitHub Push

Terraform
    |
    +-- VPC
    +-- Subnets
    +-- Security Groups
    +-- EC2
    +-- RDS
    +-- ECR
    +-- IAM
    +-- S3

**Project structure**

frontend/       Static HTML/CSS/JS calculator UI
backend/        FastAPI REST API
database/       PostgreSQL initialization script
kubernetes/     Kubernetes Deployment, Service, Secret, ConfigMap and PVC manifests
scripts/        Bash scripts for build and deployment
terraform/      AWS infrastructure using Terraform
.github/        GitHub Actions workflow

**Main Application Endpoints**

POST /calculate    Performs a calculation and stores it in PostgreSQL
GET  /health       Checks whether the backend is running

