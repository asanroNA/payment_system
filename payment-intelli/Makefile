# intelli-pay command interface (CLAUDE.md §7).
# This Makefile is the STABLE interface: every documented target exists from day one.
# Targets not yet implemented announce the slice that will fill them in, so the surface
# never changes shape — only the bodies do.
#
# NOTE: `make` is not installed by default on Windows. Install it once with:
#   winget install ezwinports.make      (or GnuWin32 Make)
# Until then, run the wrapped `uv run ...` commands directly.

.DEFAULT_GOAL := help
.PHONY: help up down reset run migrate topics schema-register schema-check \
        produce consume test test-unit lint

COMPOSE := docker compose -f infra/docker-compose.yml

help: ## List available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# --- Infra (Slice 3) ---------------------------------------------------------
up: ## Start local infra (kafka, schema-registry, postgres, ui)
	$(COMPOSE) up -d --wait

down: ## Tear down infra, keep volumes
	$(COMPOSE) down

reset: ## Tear down infra and wipe volumes (clean slate)
	$(COMPOSE) down -v

topics: ## Create/declare topics from infra/kafka/topics.txt
	@while IFS=: read -r name parts || [ -n "$$name" ]; do \
		case "$$name" in ''|\#*) continue ;; esac; \
		$(COMPOSE) exec -T kafka kafka-topics \
			--bootstrap-server localhost:9092 --create --if-not-exists \
			--topic "$$name" --partitions "$$parts" --replication-factor 1; \
	done < infra/kafka/topics.txt

# --- Services (Slice 4+) -----------------------------------------------------
run: ## Run one service locally (usage: make run svc=payment-api)
	@echo "not implemented yet (slice 4)"

migrate: ## alembic upgrade head for one service (usage: make migrate svc=payment-api)
	@echo "not implemented yet (slice 4)"

# --- Schema registry (post-foundation) ---------------------------------------
schema-register: ## Register libs/contracts schemas with the registry
	@echo "not implemented yet (post-foundation)"

schema-check: ## FAIL on any backward-incompatible schema change (CI gate)
	@echo "not implemented yet (post-foundation)"

# --- Manual event tooling (Slice 4+) -----------------------------------------
produce: ## Emit a sample event (usage: make produce e=PaymentInitiated)
	@echo "not implemented yet (slice 4)"

consume: ## Tail a topic (usage: make consume t=payments.lifecycle.events)
	@echo "not implemented yet (slice 4)"

# --- Quality gates (live now) ------------------------------------------------
lint: ## ruff check + format check + mypy --strict
	uv run ruff check .
	uv run ruff format --check .
	# Check by package (not a directory walk): with src-layout namespace packages a bare
	# `mypy .` reads `intellipay` as two module roots and errors "found twice". mypy can't
	# mix -p with file paths in one call, so tests run as a second invocation (grows per slice).
	uv run mypy -p intellipay.contracts -p intellipay.common -p app
	uv run mypy libs/contracts/tests libs/common/tests

test-unit: ## Fast tests, no infra
	uv run pytest -m "not integration"

test: ## Full suite (unit + contract + integration via testcontainers)
	uv run pytest
