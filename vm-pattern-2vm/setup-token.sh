#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ -f .env ]; then echo '.env exists; unchanged'; exit 0; fi
umask 077
printf 'INTERNAL_TOKEN=%s\n' "$(openssl rand -hex 32)" > .env
echo 'Created private .env'
