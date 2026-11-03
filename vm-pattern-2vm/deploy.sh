#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
bash setup-token.sh
docker build -t vm-pattern:3.0 .
minikube -p vm-lab image load vm-pattern:3.0
minikube -p vm-lab kubectl -- create namespace secure-app --dry-run=client -o yaml | minikube -p vm-lab kubectl -- apply -f -
minikube -p vm-lab kubectl -- -n secure-app create secret generic internal-token --from-env-file=.env --dry-run=client -o yaml | minikube -p vm-lab kubectl -- apply -f -
minikube -p vm-lab kubectl -- apply -f k8s.yaml
for role in gateway api data security audit; do
  minikube -p vm-lab kubectl -- -n secure-app rollout status deployment/"$role" --timeout=180s
done
minikube -p vm-lab kubectl -- -n secure-app get pods
