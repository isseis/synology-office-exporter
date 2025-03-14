.PHONY: run test lint

run:
	python3 main.py -o out $(ARGS)

test:
	python3 -m unittest discover -s . -p 'test_*.py'

lint:
	python3 -m flake8 .
