# Mark reading works out of the box: zxing-cpp installs from a wheel and reads
# every size we produce. zbar is a further fallback and needs a system library,
# so macOS wants its lib directory on the loader path before Python starts.
# Harmless when zbar is absent, which is the normal case.
# Tools are invoked as modules rather than as executables. `uv run pytest`
# resolves the name on PATH, so an unrelated virtualenv that happens to be
# activated supplies its own pytest, which then cannot import this project and
# fails with a wall of ModuleNotFoundError. `uv run python -m pytest` runs
# inside the interpreter uv picked, whatever else is on PATH.
ZBAR_LIB := $(shell brew --prefix zbar 2>/dev/null)/lib
export DYLD_LIBRARY_PATH := $(ZBAR_LIB):$(DYLD_LIBRARY_PATH)

.PHONY: setup check test doctor demo-loop verify clean

setup:
	uv sync
	uv run python -m pre_commit install
	uv run python -m pre_commit install --hook-type commit-msg
	uv run python -m pre_commit install --hook-type pre-push

check:
	uv run python -m ruff check src tests scripts
	uv run python -m ruff format --check src tests scripts
	uv run python -m mypy
	uv run python scripts/check_prose.py

test:
	uv run python -m pytest --cov=signet --cov-branch --cov-fail-under=80

doctor:
	uv run python scripts/check_env.py

demo-loop:
	@echo
	@echo '  Generates a key, signs a receipt, draws the mark and reads it back.'
	@echo '  The verdict will be UNSIGNED, and that is the correct answer: the key'
	@echo '  was never published to example.com, so nothing vouches for it. That is'
	@echo '  the whole point. Publishing is a separate, deliberate act.'
	@echo
	uv run python -m signet.cli keygen --domain example.com --brand "Mercer Fabrication"
	uv run python -m signet.cli issue --domain example.com --field amt=14.75 --field cur=USD --out /tmp/signet-demo.png
	-uv run python -m signet.cli verify /tmp/signet-demo.png --brand "Mercer Fabrication"

verify:
	# A flagged verdict exits 2 on purpose, which is a result rather than a
	# build failure, so make is told not to treat it as one.
	-uv run python -m signet.cli verify $(FILE)

clean:
	rm -rf .mypy_cache .ruff_cache .pytest_cache htmlcov .coverage dist build
