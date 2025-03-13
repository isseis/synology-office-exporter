.PHONY: test lint

test:
	python3 -m unittest discover -s . -p 'test_*.py'

lint:
	python3 -m flake8 .
