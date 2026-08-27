# Mark reading works out of the box: zxing-cpp installs from a wheel and reads
# every size we produce. zbar is a further fallback and needs a system library,
# so macOS wants its lib directory on the loader path before Python starts.
# Harmless when zbar is absent, which is the normal case.
ZBAR_LIB := $(shell brew --prefix zbar 2>/dev/null)/lib
export DYLD_LIBRARY_PATH := $(ZBAR_LIB):$(DYLD_LIBRARY_PATH)

.PHONY: setup check test doctor demo-loop verify clean

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

doctor:
	uv run python scripts/check_env.py

demo-loop:
	@echo
	@echo '  Generates a key, signs a receipt, draws the mark and reads it back.'
	@echo '  The verdict will be UNSIGNED, and that is the correct answer: the key'
	@echo '  was never published to example.com, so nothing vouches for it. That is'
	@echo '  the whole point. Publishing is a separate, deliberate act.'
	@echo
	uv run signet keygen --domain example.com --brand "Mercer Fabrication"
	uv run signet issue --domain example.com --field amt=14.75 --field cur=USD --out /tmp/signet-demo.png
	-uv run signet verify /tmp/signet-demo.png --brand "Mercer Fabrication"

verify:
	# A flagged verdict exits 2 on purpose, which is a result rather than a
	# build failure, so make is told not to treat it as one.
	-uv run signet verify $(FILE)

clean:
	rm -rf .mypy_cache .ruff_cache .pytest_cache htmlcov .coverage dist build
