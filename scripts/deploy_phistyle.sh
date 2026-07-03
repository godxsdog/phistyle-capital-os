#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/Users/kaichanghuang/Server/phistyle-capital-os"

cd "$REPO_DIR"

git pull origin main
git status

if [[ -f docker-compose.yml ]]; then
  docker compose up -d --build
else
  echo "No docker-compose.yml yet. Pull completed only."
fi

