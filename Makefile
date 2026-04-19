PY := .venv/bin/python
PIP := .venv/bin/pip
PYTEST := .venv/bin/pytest
RUFF := .venv/bin/ruff

.PHONY: help venv install lint fmt test cov check build clean

help:
	@echo "make venv     - create .venv and install in dev mode"
	@echo "make install  - re-install package with dev extras"
	@echo "make lint     - ruff check"
	@echo "make fmt      - ruff format"
	@echo "make test     - run pytest"
	@echo "make cov      - run pytest with coverage + 85% gate"
	@echo "make check    - lint + test (what CI does)"
	@echo "make build    - build sdist + wheel into dist/"
	@echo "make clean    - wipe build artifacts"

venv:
	python3.12 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -e '.[dev]'

install:
	$(PIP) install -e '.[dev]'

lint:
	$(RUFF) check easyatcal tests

fmt:
	$(RUFF) format easyatcal tests
	$(RUFF) check --fix easyatcal tests

test:
	$(PYTEST)

cov:
	$(PYTEST) --cov=easyatcal --cov-fail-under=85

check: lint cov

build:
	$(PY) -m pip install --upgrade build
	$(PY) -m build

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache .coverage htmlcov
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
