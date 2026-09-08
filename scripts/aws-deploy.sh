#!/bin/bash
set -e

# Run this script on the EC2 instance. It pulls the latest images from ECR
# and (re)starts the frontend and backend containers, pointing the backend
# at the RDS PostgreSQL instance created by Terraform.
#
# Required environment variables (export these before running, or put them
# in a .env file on the EC2 instance and `source .env` first):
#   AWS_ACCOUNT_ID   - your AWS account ID
#   AWS_REGION       - e.g. us-east-1
#   RDS_ENDPOINT     - RDS endpoint hostname (from terraform output rds_endpoint)
#   POSTGRES_DB      - e.g. calculator
#   POSTGRES_USER    - e.g. calculator
#   POSTGRES_PASSWORD

: "${AWS_ACCOUNT_ID:?Set AWS_ACCOUNT_ID}"
: "${AWS_REGION:?Set AWS_REGION}"
: "${RDS_ENDPOINT:?Set RDS_ENDPOINT}"
: "${POSTGRES_DB:?Set POSTGRES_DB}"
: "${POSTGRES_USER:?Set POSTGRES_USER}"
: "${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD}"

ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

echo "Logging in to ECR..."
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR_REGISTRY"

echo "Pulling latest images..."
docker pull "${ECR_REGISTRY}/calculator-backend:latest"
docker pull "${ECR_REGISTRY}/calculator-frontend:latest"

echo "Removing old containers (if any)..."
docker rm -f backend frontend 2>/dev/null || true

docker network create calculator-net 2>/dev/null || true

echo "Starting backend..."
docker run -d \
  --name backend \
  --network calculator-net \
  -p 8000:8000 \
  -e POSTGRES_HOST="$RDS_ENDPOINT" \
  -e POSTGRES_PORT=5432 \
  -e POSTGRES_DB="$POSTGRES_DB" \
  -e POSTGRES_USER="$POSTGRES_USER" \
  -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  --restart unless-stopped \
  "${ECR_REGISTRY}/calculator-backend:latest"

echo "Starting frontend..."
docker run -d \
  --name frontend \
  --network calculator-net \
  -p 80:80 \
  -e API_URL="http://localhost:8000" \
  --restart unless-stopped \
  "${ECR_REGISTRY}/calculator-frontend:latest"

echo "Done. Containers running:"
docker ps
