.PHONY: run build install install-dev uninstall test lint clean

run:
	python -m synology_office_exporter.main -o out $(ARGS)

build:
	pip install build
	python -m build

install:
	pip install .

install-dev:
	pip install -e .

uninstall:
	pip uninstall synology-office-exporter

test:
	python -m unittest discover -s . -p 'test_*.py'

lint:
	flake8 --config .flake8

clean:
	rm -rf build dist synology_office_exporter.egg-info