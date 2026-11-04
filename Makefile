.PHONY: test lint format compliance validate eval-help

test:
	uv run pytest -q

lint:
	uv run ruff check datamate tests scripts research kaggle
	uv run ruff format --check datamate tests scripts research kaggle

format:
	uv run ruff format datamate tests scripts research kaggle
	uv run ruff check --fix datamate tests scripts research kaggle

compliance:
	uv run python scripts/check_compliance.py

# make validate PRED=runs/x/predictions.jsonl Q=data/public_test/questions.jsonl
validate:
	uv run python -m datamate.eval.validate $(PRED) --questions $(Q)

eval-help:
	@echo "uv run python -m datamate.eval.scorer --pred <pred.jsonl> --gold data/train/answers.jsonl [--ids <ids.txt>]"
