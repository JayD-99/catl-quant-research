PYTHON ?= .venv/bin/python

.PHONY: install download filings build analyze report test all

install:
	$(PYTHON) -m pip install -e .[dev]

download:
	$(PYTHON) -m catl_quant.cli download --config config/research.yaml

filings:
	$(PYTHON) scripts/download_filings.py

build:
	$(PYTHON) -m catl_quant.cli build --config config/research.yaml

analyze:
	$(PYTHON) -m catl_quant.cli analyze --config config/research.yaml

report:
	$(PYTHON) -m catl_quant.cli report --config config/research.yaml

test:
	$(PYTHON) -m pytest

all: download build analyze report test
