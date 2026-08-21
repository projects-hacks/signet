.PHONY: setup check test gate demo verify clean

setup:
	uv sync
	uv run pre-commit install
	uv run pre-commit install --hook-type commit-msg

check:
	uv run ruff check src tests scripts
	uv run ruff format --check src tests scripts
	uv run mypy
	uv run python scripts/check_prose.py

test:
	uv run pytest --cov=signet --cov-branch --cov-fail-under=80

gate:
	uv run python scripts/gates/forge.py
	uv run python scripts/gates/qr_photo.py
	uv run python scripts/gates/extraction.py
	uv run python scripts/gates/live_apis.py

demo:
	uv run python scripts/seed_demo.py

verify:
	uv run signet verify $(FILE)

clean:
	rm -rf .mypy_cache .ruff_cache .pytest_cache htmlcov .coverage dist build
