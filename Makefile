.PHONY: run test lint

run:
	python3 drive_export.py --log-level info -o out

test:
	python3 -m unittest discover -s . -p 'test_*.py'

lint:
	python3 -m flake8 .
