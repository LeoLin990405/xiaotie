#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found"
  exit 1
fi

if ! command -v pip >/dev/null 2>&1; then
  echo "pip not found"
  exit 1
fi

if ! command -v pytest >/dev/null 2>&1; then
  echo "pytest not found"
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found"
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose not available"
  exit 1
fi

python3 -m pip install --upgrade pip
pip install -e ".[dev]"
pytest -q
python3 benchmarks/agent_perf_benchmark.py
docker compose -f deployment/docker-compose.prod.yml config >/dev/null
docker compose -f deployment/docker-compose.prod.yml up -d
