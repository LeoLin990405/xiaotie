#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 未找到，请先安装 Python 3.10+"
  exit 1
fi

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate

python -m pip install -U pip
python -m pip install -e ".[dev,tui,secrets,repomap]"

if [ ! -f "config/config.yaml" ]; then
  cp config/config.yaml.example config/config.yaml
fi

echo
echo "已完成本地初始化。"
echo "下一步："
echo "  1) export MIMO_API_KEY='你的key'"
echo "  2) xiaotie   或   xiaotie --tui"
