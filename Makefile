all: help

.PHONY: lint
lint:  ## Lint Python code
	uv run ruff check .

.PHONY: format
format:  ## Format Python code
	uv run ruff format .

.PHONY: typecheck
typecheck:  ## Typecheck Python code
	uv run ty check

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'
