# Development Guide

This guide is for developers who want to contribute to the Synology Office Exporter project.

## Development Environment Setup

### Create Virtual Environment

It's recommended to create a Python virtual environment and run the tools inside it.

For bash / zsh users:
```bash
python -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
```

### Clone the Repository

```bash
git clone https://github.com/isseis/synology-office-exporter.git
cd synology-office-exporter
```

### Install Development Packages

```bash
pip install -e '.[dev]'
```

This installs packages used for development and installs this project in editable mode.
After installation, you can run the tool using the command:

```bash
synology-office-exporter --help
```

## Development Workflow

### Setting Up Pre-commit Hooks

Install the pre-commit hooks:

```bash
pre-commit install
```

Now, every time you run `git commit`, the following actions will be performed automatically:

1. Basic checks (trailing whitespaces, file endings, etc.)
2. Linting with flake8
3. Running all tests

If any of these checks fail, the commit will be aborted.

To manually run all hooks on all files:

```bash
pre-commit run --all-files
```

To skip pre-commit hooks for a specific commit (not recommended for normal workflow):

```bash
git commit --no-verify
```

### Running Tests

To run the tests manually:

```bash
make test
```

or

```bash
python -m unittest discover -s tests -p 'test_*.py'
```

### Checking Test Coverage

To check test coverage, you can use the `coverage` package:

```bash
# Run tests with coverage
coverage run -m unittest discover -s tests -p 'test_*.py'

# Generate coverage report
coverage report -m

# Generate HTML coverage report for detailed analysis
coverage html
```

Alternatively, you can use the provided make commands for a more streamlined approach:

```bash
# Run tests with coverage
make coverage

# Generate HTML coverage report
make coverage-html
```

The HTML report will be created in the `htmlcov` directory. Open `htmlcov/index.html` in your browser to view detailed coverage information for each file.

Aim for maintaining a high test coverage (ideally above 80%) to ensure code quality and reliability. Pay special attention to complex logic paths and edge cases when writing tests.

### Linting

To check code style with flake8:

```bash
make lint
```

or

```bash
flake8 --config .flake8
```

## Project Structure

- `synology_office_exporter/` - Main package directory
  - `__init__.py` - Package initialization
  - `exporter.py` - Core functionality for exporting files
  - `synology_drive_api.py` - API client for Synology Drive
  - `cli.py` - Command line interface
- `tests/` - Test directory
  - `test_*.py` - Test files

## Pull Request Process

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

Please ensure your code passes all tests and follows the project's coding style before submitting a pull request.

## Release Process

1. Update version in `setup.py`
2. Update CHANGELOG.md
3. Tag the commit with the version number
4. Push to GitHub
5. Create a new release on GitHub
6. The CI/CD pipeline will automatically publish to PyPI
