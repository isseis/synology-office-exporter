.PHONY: run test lint clean

run:
	python3 main.py -o out $(ARGS)

test:
	python3 -m unittest discover -s . -p 'test_*.py'

lint:
	python3 -m flake8 .

clean:
	rm -rf dist synology_office_exporter.egg-info