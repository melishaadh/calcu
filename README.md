Calculator App — DevOps Learning Project

A simple calculator application built to practice a complete DevOps workflow using Docker, Docker Compose, Kubernetes, Terraform, GitHub Actions, and AWS.

Every calculation is sent from the frontend to the backend, processed by the FastAPI API, stored in PostgreSQL, and the result is returned to the frontend.

Architecture
Application Architecture
Frontend (HTML/CSS/JS)
          |
          v
Backend (FastAPI)
          |
          v
PostgreSQL

Every calculation follows this flow:

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
Production Architecture on AWS
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

Terraform is used to provision the AWS infrastructure, while GitHub Actions builds Docker images and pushes them to Amazon ECR.

Project Structure
frontend/       Static HTML/CSS/JS calculator UI
backend/        FastAPI REST API
database/       PostgreSQL initialization script
kubernetes/     Kubernetes Deployment, Service, Secret, ConfigMap and PVC manifests
scripts/        Bash scripts for build and deployment
terraform/      AWS infrastructure using Terraform
.github/        GitHub Actions workflow
Main Application Endpoints
POST /calculate    Performs a calculation and stores it in PostgreSQL
GET  /health       Checks whether the backend is running
Technologies Used
Technology	Purpose
HTML/CSS/JavaScript	Frontend
FastAPI	Backend REST API
Python	Backend programming language
PostgreSQL	Database
Docker	Containerization
Docker Compose	Local multi-container environment
Kubernetes	Container orchestration
Terraform	Infrastructure as Code
AWS EC2	Application server
AWS RDS	Managed PostgreSQL database
Amazon ECR	Docker image registry
AWS IAM	Access control
AWS VPC	Network infrastructure
Amazon S3	Cloud storage resource
GitHub Actions	CI and image delivery
GitHub OIDC	Secure AWS authentication
Bash	Deployment automation
Git	Version control
Run Locally with Docker Compose

Copy the example environment file:

cp .env.example .env

Start the application:

docker compose up --build

The application will be available at:

Frontend: http://localhost:3000
Backend:  http://localhost:8000/health
Postgres: localhost:5432

The Docker Compose environment runs:

Frontend Container
       |
       v
Backend Container
       |
       v
PostgreSQL Container
Stop the application
docker compose down
Stop the application and remove the database volume
docker compose down -v

The -v option removes the PostgreSQL volume and therefore deletes the locally stored database data.

Docker

The project uses separate Docker images for the frontend and backend.

Build both images:

./scripts/docker-build.sh

The images are:

backend:latest
frontend:latest

Docker provides:

Application isolation
Portable environments
Reproducible builds
Consistent deployment
Easy application packaging
Bash Scripts

The project includes Bash scripts to automate common DevOps operations.

scripts/docker-build.sh
scripts/kubernetes-deploy.sh
scripts/kubernetes-delete.sh
scripts/aws-deploy.sh
Script purposes
docker-build.sh
    Builds the backend and frontend Docker images

kubernetes-deploy.sh
    Deploys the application to Kubernetes

kubernetes-delete.sh
    Removes the Kubernetes resources

aws-deploy.sh
    Pulls images from ECR and starts the application containers on EC2

Make the scripts executable:

chmod +x scripts/*.sh
Kubernetes

Kubernetes is used to demonstrate container orchestration.

The Kubernetes configuration contains:

Frontend Deployment
Frontend Service

Backend Deployment
Backend Service

PostgreSQL Deployment
PostgreSQL Service
PostgreSQL PVC

ConfigMap
Secret

The local Kubernetes architecture is:

              Kubernetes Cluster
                     |
          +----------+----------+
          |                     |
      Frontend               Backend
      Deployment             Deployment
          |                     |
       Service                Service
                                |
                                v
                           PostgreSQL
                           Deployment
                                |
                              PVC

The backend and frontend deployments use multiple replicas to demonstrate horizontal scaling.

Deploy the application

Make sure the local Docker images have been built:

./scripts/docker-build.sh

Deploy the Kubernetes resources:

./scripts/kubernetes-deploy.sh

Check the deployments:

kubectl get deployments

Check the pods:

kubectl get pods

Check the services:

kubectl get services

The application can be accessed using:

Frontend: http://localhost:30300
Backend:  http://localhost:30800/health
Remove Kubernetes Resources
./scripts/kubernetes-delete.sh

Resources created by Kubernetes include:

app-config ConfigMap
postgres-init ConfigMap
app-secret Secret
postgres-pvc PersistentVolumeClaim

postgres Deployment
backend Deployment
frontend Deployment

postgres Service
backend Service
frontend Service
GitHub Actions

The project uses GitHub Actions to automate the Docker image build and delivery process.

The workflow is triggered when code is pushed to the main branch.

The workflow performs:

Git Push
    |
    v
GitHub Actions
    |
    v
Authenticate with AWS using OIDC
    |
    v
Login to Amazon ECR
    |
    +--------------------+
    |                    |
    v                    v
Build Backend       Build Frontend
    |                    |
    v                    v
Push to ECR          Push to ECR

The images are pushed to:

calculator-backend
calculator-frontend

Each image is tagged with:

latest
Git commit SHA

For example:

calculator-backend:latest
calculator-backend:<commit-sha>

calculator-frontend:latest
calculator-frontend:<commit-sha>

The commit SHA makes it possible to identify which source-code version produced an image.

AWS Authentication

GitHub Actions uses AWS IAM and OpenID Connect (OIDC).

Long-lived AWS access keys are not stored in the GitHub Actions workflow.

Instead:

GitHub Actions
      |
      v
GitHub OIDC
      |
      v
AWS IAM Role
      |
      v
Temporary AWS Credentials
      |
      v
Amazon ECR

This provides a more secure authentication method for the CI pipeline.

Terraform — AWS Infrastructure

Terraform is used as Infrastructure as Code to provision the AWS environment.

The Terraform configuration manages:

VPC
Public Subnet
Private Subnets
Internet Gateway
Route Table
Security Groups

EC2
RDS PostgreSQL
ECR Repositories
IAM Roles
S3 Bucket

The AWS architecture separates the application server and database:

Public Subnet
     |
     v
    EC2
     |
     | PostgreSQL connection
     v
Private Subnet
     |
     v
    RDS

The RDS database is placed in private subnets and is not directly exposed to the public Internet.

Initialize Terraform
cd terraform
terraform init

Validate the configuration:

terraform validate

Create an execution plan:

terraform plan

Apply the infrastructure:

terraform apply \
  -var="db_password=YOUR_STRONG_PASSWORD" \
  -var="key_name=YOUR_EC2_KEY_PAIR_NAME"

key_name must be an existing EC2 key pair used for SSH access.

Terraform Outputs

After deployment, Terraform provides important information such as:

ECR backend repository URL
ECR frontend repository URL
EC2 public IP
RDS endpoint
S3 bucket name

View outputs:

terraform output
Destroy the Infrastructure

When the AWS environment is no longer required:

terraform destroy
AWS Deployment

The production application runs on an EC2 instance.

The deployment process is:

Source Code
     |
     v
GitHub
     |
     v
GitHub Actions
     |
     v
Amazon ECR
     |
     v
EC2
     |
     +------------+
     |            |
     v            v
 Frontend      Backend
 Container     Container
                   |
                   v
              RDS PostgreSQL
Deploying to EC2
Create the AWS infrastructure using Terraform.
Build and push the Docker images to ECR using GitHub Actions.
SSH into the EC2 instance.
Configure the required environment variables.
export AWS_ACCOUNT_ID=<your-account-id>
export AWS_REGION=us-east-1
export RDS_ENDPOINT=<terraform-rds-endpoint>
export POSTGRES_DB=calculator
export POSTGRES_USER=calculator
export POSTGRES_PASSWORD=<your-db-password>
Run the deployment script:
./scripts/aws-deploy.sh
Verify the running containers:
docker ps
Test the backend:
curl http://localhost:8000/health
Open the application using the EC2 public IP:
http://<ec2-public-ip>
Database

The application uses PostgreSQL to store calculation history.

The database contains a calculations table with fields including:

id
operation
a
b
result
created_at

Every calculation performed by the application is sent to the backend and stored in PostgreSQL.

Local Database

The local Docker Compose environment uses a PostgreSQL container with persistent storage.

Kubernetes Database

The Kubernetes environment uses:

PostgreSQL Deployment
        |
        v
PersistentVolumeClaim

This allows database data to persist beyond individual container restarts.

AWS Database

The production environment uses Amazon RDS PostgreSQL.

The backend connects to RDS through the private AWS network.

EC2 Backend
     |
     | Port 5432
     v
RDS PostgreSQL

The RDS Security Group only allows PostgreSQL traffic from the application server's Security Group.

Environment Variables

The application uses environment variables for environment-specific configuration.

Important variables include:

POSTGRES_HOST
POSTGRES_PORT
POSTGRES_DB
POSTGRES_USER
POSTGRES_PASSWORD
API_URL
AWS_REGION
RDS_ENDPOINT

Environment variables prevent environment-specific configuration from being hard-coded into the application.

Sensitive values such as database passwords should not be committed to Git.

Security

The project demonstrates several basic cloud security practices.

IAM

IAM roles are used to provide AWS permissions to services without storing permanent credentials inside application code.

The EC2 instance has an IAM role that allows it to pull images from Amazon ECR.

GitHub OIDC

GitHub Actions uses OIDC to authenticate with AWS instead of storing long-lived AWS access keys.

Security Groups

AWS Security Groups control network traffic between the application and database.

The RDS database only accepts PostgreSQL connections from the application environment.

Private Database

RDS is deployed in private subnets rather than being directly accessible from the Internet.

Sensitive Files

The following types of files should not be committed to Git:

.env
terraform.tfvars
*.tfstate
*.pem

These are protected through .gitignore.

Major DevOps Concepts Demonstrated

This project demonstrates the following major DevOps concepts:

1. Version Control

Git and GitHub are used to track application and infrastructure changes.

Developer
    |
    v
Git
    |
    v
GitHub
2. Containerization

Docker packages the application and its dependencies into portable containers.

Frontend → Docker Container
Backend  → Docker Container
Database → Docker Container
3. Container Orchestration

Kubernetes manages application containers using Deployments, Services, replicas, Secrets, ConfigMaps, and persistent storage.

4. Infrastructure as Code

Terraform defines AWS infrastructure using configuration files instead of manually creating resources.

Terraform
    |
    +-- VPC
    +-- EC2
    +-- RDS
    +-- ECR
    +-- IAM
    +-- S3
5. Continuous Integration

GitHub Actions automatically builds Docker images when changes are pushed to the main branch.

6. Continuous Delivery

Built Docker images are automatically pushed to Amazon ECR, making new application versions available for deployment to EC2.

7. Cloud Computing

AWS provides the production infrastructure:

EC2
RDS
ECR
IAM
VPC
S3
8. Cloud Networking

The project demonstrates:

VPC
Public subnets
Private subnets
Internet Gateway
Route tables
Security Groups
Private database networking
9. IAM and Access Control

IAM roles and policies control which AWS resources services can access.

10. Secrets and Configuration Management

Environment variables, Kubernetes Secrets, and protected configuration are used to keep environment-specific and sensitive values outside application code.

11. Automation

Bash scripts and GitHub Actions automate repetitive build and deployment tasks.

12. Declarative Infrastructure

Terraform and Kubernetes use declarative configuration.

Instead of manually performing every step, the desired infrastructure or application state is defined in configuration files.

13. Scalability

Kubernetes Deployments use multiple replicas for the frontend and backend.

This demonstrates horizontal scaling at the container level.

14. Persistent Storage

Different environments use appropriate storage mechanisms:

Docker Compose
    → Docker Volume

Kubernetes
    → PersistentVolumeClaim

AWS
    → RDS Managed Storage
15. Health Checks and Validation

The backend provides:

GET /health

Deployment validation can be performed using:

docker ps
kubectl get pods
kubectl get services
curl http://localhost:8000/health
16. Reproducible Deployments

The combination of Docker, Kubernetes, Terraform, GitHub Actions, and Bash scripts makes the application deployment process repeatable.

Troubleshooting
Backend cannot connect to PostgreSQL

Check that the database environment variables are correct:

POSTGRES_HOST
POSTGRES_PORT
POSTGRES_DB
POSTGRES_USER
POSTGRES_PASSWORD

For Docker Compose, the PostgreSQL service name should be used as the database host.

For AWS, the RDS endpoint should be used.

Frontend shows "Could not reach backend"

Check the API_URL configuration.

The API URL must point to a backend address that is reachable from the browser.

For Docker:

frontend/config.js

For Kubernetes:

app-config ConfigMap

For AWS, verify that the frontend is configured with the reachable EC2 backend address.

Kubernetes pods are stuck in ImagePullBackOff

Check the pods:

kubectl get pods

For the local Kubernetes setup, make sure the required Docker images exist:

docker images

Build them again if necessary:

./scripts/docker-build.sh

The local Kubernetes manifests use the locally built:

backend:latest
frontend:latest
RDS connection refused from EC2

Check:

EC2 and RDS are in the same VPC.
The RDS Security Group allows TCP port 5432.
The RDS Security Group allows traffic from the EC2 application Security Group.
The RDS endpoint is correct.
The PostgreSQL username, database name, and password are correct.
Check running EC2 containers
docker ps

View backend logs:

docker logs backend

View frontend logs:

docker logs frontend
Complete DevOps Workflow

The complete project workflow is:

                    Developer
                        |
                        v
                   Git / GitHub
                        |
                        v
                 GitHub Actions
                        |
              OIDC Authentication
                        |
                        v
                     AWS IAM
                        |
                        v
                  Docker Build
                   /        \
                  /          \
                 v            v
          Backend Image   Frontend Image
                 \            /
                  \          /
                   v        v
                  Amazon ECR
                       |
                       v
                      EC2
                +------+------+
                |             |
                v             v
           Frontend       Backend
                            |
                            v
                       RDS PostgreSQL

Infrastructure is managed separately through Terraform:

                    Terraform
                        |
        +---------------+---------------+
        |               |               |
        v               v               v
       VPC             EC2             RDS
        |               |               |
        v               v               v
    Networking       ECR Access     PostgreSQL
                        |
                        v
                       IAM
What This Project Demonstrates

By completing this project, the following DevOps workflow has been implemented:

Code
 |
 v
GitHub
 |
 v
CI with GitHub Actions
 |
 v
Docker Build
 |
 v
Amazon ECR
 |
 v
EC2 Deployment
 |
 v
FastAPI Backend
 |
 v
RDS PostgreSQL

Alongside the application pipeline:

Terraform
    |
    v
AWS Infrastructure
    |
    +-- VPC
    +-- Networking
    +-- Security Groups
    +-- EC2
    +-- RDS
    +-- ECR
    +-- IAM
    +-- S3

The project therefore demonstrates practical experience with containerization, CI/CD, Infrastructure as Code, cloud deployment, Kubernetes, networking, IAM, security, automation, configuration management, persistent storage, scalability, and deployment troubleshooting.

Project Goal

The goal of this project is not the calculator itself, but learning how a software application can move from local development to a containerized environment, Kubernetes, and finally a cloud-based AWS deployment using modern DevOps practices.

The project demonstrates the complete path:

Development
     |
     v
Docker
     |
     v
Docker Compose
     |
     v
Kubernetes
     |
     v
Terraform
     |
     v
AWS
     |
     v
GitHub Actions
     |
     v
ECR
     |
     v
EC2 + RDS
