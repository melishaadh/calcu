#!/bin/bash
set -e

echo "Deleting Kubernetes resources..."
kubectl delete -f kubernetes/frontend-service.yaml --ignore-not-found
kubectl delete -f kubernetes/frontend-deployment.yaml --ignore-not-found
kubectl delete -f kubernetes/backend-service.yaml --ignore-not-found
kubectl delete -f kubernetes/backend-deployment.yaml --ignore-not-found
kubectl delete -f kubernetes/postgres-service.yaml --ignore-not-found
kubectl delete -f kubernetes/postgres-deployment.yaml --ignore-not-found
kubectl delete -f kubernetes/postgres-pvc.yaml --ignore-not-found
kubectl delete -f kubernetes/secret.yaml --ignore-not-found
kubectl delete -f kubernetes/configmap.yaml --ignore-not-found

echo "Done."
