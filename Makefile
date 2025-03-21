.PHONY: run build coverage coverage-html install install-dev uninstall test lint venv-setup pre-commit upload-test clean

build:
	pip install build
	python -m build

run:
	synology-office-exporter -o out $(ARGS)

install:
	pip install .

install-dev:
	pip install -e '.[dev]'

uninstall:
	pip uninstall synology-office-exporter

test:
	python -m unittest discover -s tests -p 'test_*.py'

coverage:
	coverage run -m unittest discover -s tests -p 'test_*.py'
	coverage report -m

coverage-html:
	coverage run -m unittest discover -s tests -p 'test_*.py'
	coverage html

lint:
	flake8 --config .flake8

venv-setup:
	python -m venv .venv
	.venv/bin/pip install --upgrade pip

pre-commit:
	pre-commit run --all-files

upload-test: build
	twine upload --repository testpypi dist/*

clean:
	rm -rf build dist synology_office_exporter.egg-info
