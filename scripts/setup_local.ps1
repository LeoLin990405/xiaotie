$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  Write-Host "python 未找到，请先安装 Python 3.10+"
  exit 1
}

if (-not (Test-Path ".venv")) {
  python -m venv .venv
}

. .\.venv\Scripts\Activate.ps1

python -m pip install -U pip
python -m pip install -e ".[dev,tui,secrets,repomap]"

if (-not (Test-Path "config\config.yaml")) {
  Copy-Item "config\config.yaml.example" "config\config.yaml"
}

Write-Host ""
Write-Host "已完成本地初始化。"
Write-Host "下一步："
Write-Host "  1) `$env:MIMO_API_KEY='你的key'"
Write-Host "  2) xiaotie   或   xiaotie --tui"
