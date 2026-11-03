#!/usr/bin/env bash
set -euo pipefail
exec minikube -p vm-lab kubectl -- -n secure-app port-forward \
  --address 127.0.0.1,192.168.50.20 service/gateway 8080:8000
