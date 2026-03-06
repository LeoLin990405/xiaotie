.PHONY: test lint format security-scan benchmark ci-local clean help

PYTHON ?= python3

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

test: ## Run tests with coverage
	$(PYTHON) -m pytest tests/ -v --tb=short

lint: ## Run ruff linter
	ruff check xiaotie/

format: ## Format code with ruff
	ruff format xiaotie/ tests/

format-check: ## Check formatting without modifying
	ruff format --check xiaotie/

security-scan: ## Run bandit SAST + pip-audit
	bandit -r xiaotie/ -c pyproject.toml --severity-level medium
	pip-audit --strict --desc

benchmark: ## Run performance benchmarks
	$(PYTHON) benchmarks/agent_perf_benchmark.py

ci-local: lint format-check test security-scan ## Run full CI pipeline locally
	@echo "\n\033[32mAll CI checks passed.\033[0m"

clean: ## Remove build artifacts and caches
	rm -rf build/ dist/ *.egg-info htmlcov/ .pytest_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
