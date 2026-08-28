#!/usr/bin/env bash
#
# fix_and_deploy.sh
#
# Fixes the InvalidImageName errors in k8s/*.yaml (leftover
# DOCKERHUB_USERNAME_PLACEHOLDER / IMAGE_TAG_PLACEHOLDER / registry prefixes),
# builds every microservice straight into Minikube's own Docker daemon under
# simple local tags, applies the manifests, and reports pod status.
#
# Usage: ./fix_and_deploy.sh
# Must be run from the root of the calcu/ repo (where k8s/ lives).

set -euo pipefail

NAMESPACE="calcu"
K8S_DIR="k8s"

# service-name:build-context pairs — the local image tag on the left must
# match the "image:" value in k8s/deployments-and-services.yaml after
# sanitization.
SERVICES=(frontend financial-engine history-service scientific-engine)
CONTEXTS=(./frontend ./services/financial-engine ./services/history-service ./services/scientific-engine)

echo "=================================================="
echo " STEP 1/4 — Sanitizing image references in ${K8S_DIR}/*.yaml"
echo "=================================================="

if ! compgen -G "${K8S_DIR}"/*.yaml > /dev/null; then
    echo "ERROR: no .yaml files found in ${K8S_DIR}/ — are you in the calcu/ repo root?" >&2
    exit 1
fi

for f in "${K8S_DIR}"/*.yaml; do
    echo "  -> ${f}"

    # 1a. Strip known registry / username placeholders outright.
    sed -i \
        -e 's#DOCKERHUB_USERNAME_PLACEHOLDER/##g' \
        -e 's#melishaadh/##g' \
        -e 's#REPLACE_ECR_REGISTRY/##g' \
        "${f}"

    # 1b. Catch-all: strip ANY remaining "somehost-or-user/" prefix directly
    # in front of an image name, in case a different registry was set manually.
    sed -i -E 's#(image: *)[^[:space:]/]+/#\1#' "${f}"

    # 1c. Strip the "calcu-" prefix from image names (calcu-frontend -> frontend, etc.)
    sed -i -E 's#(image: *)calcu-#\1#' "${f}"

    # 1d. Standardize the tag to :latest for each of our four services only
    # (this deliberately does NOT touch unrelated images like postgres:16-alpine).
    for svc in "${SERVICES[@]}"; do
        sed -i -E "s#(image: *${svc}):[^[:space:]]*#\1:latest#g" "${f}"
    done

    # 1e. Force imagePullPolicy: IfNotPresent on every container so Kubernetes
    # uses the image already loaded into Minikube's Docker daemon instead of
    # trying to pull it from a registry. Drop any existing line first so
    # re-running this script never produces duplicates, then re-insert one
    # correctly-indented copy right after every "image:" line.
    sed -i '/imagePullPolicy:/d' "${f}"
    sed -i -E 's/^([ ]*)(image: .*)$/\1\2\
\1imagePullPolicy: IfNotPresent/' "${f}"
done

echo
echo "Result:"
grep -n "image:\|imagePullPolicy:" "${K8S_DIR}"/*.yaml
echo

echo "=================================================="
echo " STEP 2/4 — Pointing Docker at Minikube's daemon"
echo "=================================================="

if ! command -v minikube >/dev/null 2>&1; then
    echo "ERROR: 'minikube' not found on PATH." >&2
    exit 1
fi

if ! minikube status >/dev/null 2>&1; then
    echo "Minikube isn't running yet — starting it..."
    minikube start
fi

eval "$(minikube docker-env)"
echo "Docker CLI now targets Minikube's internal daemon."

echo
echo "=================================================="
echo " STEP 3/4 — Building images locally"
echo "=================================================="

for i in "${!SERVICES[@]}"; do
    svc="${SERVICES[$i]}"
    ctx="${CONTEXTS[$i]}"
    echo "  -> building ${svc}:latest from ${ctx}"
    docker build -t "${svc}:latest" "${ctx}"
done

echo
echo "=================================================="
echo " STEP 4/4 — Deploying to Kubernetes"
echo "=================================================="

kubectl apply -f "${K8S_DIR}/"

echo "Waiting 5s for pods to be scheduled..."
sleep 5

echo
echo "Pod status in namespace '${NAMESPACE}':"
kubectl get pods -n "${NAMESPACE}"

echo
echo "Done. If any pod isn't Running yet, check with:"
echo "  kubectl describe pod <pod-name> -n ${NAMESPACE}"
echo "  kubectl logs <pod-name> -n ${NAMESPACE}"
