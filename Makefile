.PHONY: run build install install-dev uninstall test lint clean

build:
	pip install build
	python -m build

run:
	python -m synology_office_exporter.main -o out $(ARGS)

install:
	pip install .

install-dev:
	pip install -e .

uninstall:
	pip uninstall synology-office-exporter

test:
	python -m unittest discover -s tests -p 'test_*.py'

lint:
	flake8 --config .flake8

clean:
	rm -rf build dist synology_office_exporter.egg-info