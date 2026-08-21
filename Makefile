# macOS reads DYLD_LIBRARY_PATH at process start, so zbar has to be on it
# before Python runs. Harmless where zbar is on the default loader path.
ZBAR_LIB := $(shell brew --prefix zbar 2>/dev/null)/lib
export DYLD_LIBRARY_PATH := $(ZBAR_LIB):$(DYLD_LIBRARY_PATH)

.PHONY: setup check test doctor gate demo demo-loop verify clean

setup:
	@command -v brew >/dev/null && brew list zbar >/dev/null 2>&1 || echo 'note: install zbar for reliable QR decoding (brew install zbar)'
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

doctor:
	uv run python scripts/check_env.py

gate:
	uv run python scripts/gates/forge.py
	uv run python scripts/gates/qr_photo.py
	uv run python scripts/gates/extraction.py
	uv run python scripts/gates/live_apis.py

demo-loop:
	uv run signet keygen --domain example.com --brand "Mercer Fabrication"
	uv run signet issue --domain example.com --field amt=14.75 --field cur=USD --out /tmp/signet-demo.png
	-uv run signet verify /tmp/signet-demo.png --brand "Mercer Fabrication"

demo:
	uv run python scripts/seed_demo.py

verify:
	# A flagged verdict exits 2 on purpose, which is a result rather than a
	# build failure, so make is told not to treat it as one.
	-uv run signet verify $(FILE)

clean:
	rm -rf .mypy_cache .ruff_cache .pytest_cache htmlcov .coverage dist build
