# Development Guide

This guide is for developers who want to contribute to the Synology Office Exporter project.

## Development Environment Setup

### Clone the Repository

```bash
git clone https://github.com/isseis/synology-office-exporter.git
cd synology-office-exporter
```

### Create Virtual Environment

It's recommended to create a Python virtual environment to isolate your development dependencies.

For bash / zsh users:
```bash
# This command only needs to be run once to create the virtual environment
python -m venv .venv

# This command must be run each time you open a new terminal session for development
source .venv/bin/activate
```

This creates a virtual environment in the `.venv` directory (one-time setup) and activates it (required each time you start a new development session), ensuring all Python packages are installed locally without affecting your global Python installation.

You should also consider using [direnv](https://direnv.net/) to run `. .venv/bin/activivate` when you enter the directory and reset the environment variables when you move out of the directory automatically.

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

## Build and Deployment

### Automated procedure

This project uses GitHub Actions for build and deployment.
To create a new release, you just need to take the following steps.

1. Commit and push changes
2. Create and push a new tag: `git tag vX.Y.Z && git push --tags`
3. The CI/CD pipeline will automatically build, publish to PyPI and create release on GitHub.

The workflow is defined in `.github/workflows/` and includes:
- Running tests on multiple Python versions
- Code quality checks
- Building and publishing the package

### Manual procedure

#### Building the Package

To build the package locally:

```bash
# Clean any previous builds
rm -rf build/ dist/ *.egg-info/

# Build the package
python -m build
```

This will create both source distribution (`.tar.gz`) and wheel (`.whl`) files in the `dist/` directory.

Alternatively, you can execute `make clean && make build`.

#### Testing the Package Locally

You can install the locally built package for testing:

```bash
pip install dist/*.whl
```

#### Deploying to PyPI (Test)

For testing the deployment process, you can use the PyPI test environment:

```bash
python -m twine upload --repository testpypi dist/*
```

The package will be available at: https://test.pypi.org/project/synology-office-exporter/

#### Deploying to PyPI (Production)

Once you've verified the package works correctly on TestPyPI, you can deploy to the main PyPI repository:

```bash
python -m twine upload dist/*
```

## File Formats

### Download History File

The download history is stored in a JSON file to track which files have been previously downloaded. By default, this file is named `.download_history.json` and is stored in the output directory (e.g., `out/.download_history.json`).

Based on the actual implementation, the file format is as follows:
```json
{
  "_meta": {
    "version": 1,
    "magic": "SYNOLOGY_OFFICE_EXPORTER_HISTORY",
    "created": "2023-09-15T22:14:32.456789",
    "generator": "synology-office-exporter 0.1.0"
  },
  "files": {
    "/mydrive/sample.odoc": {
      "file_id": "873625468996202503",
      "hash": "fa114872a44e2741aad1840202a096e5",
      "download_time": "2025-03-22 15:52:38.543378"
    },
    "/shared-with-me/Documents/test5.odoc": {
      "file_id": "873441590473964286",
      "hash": "83481ff648006182790a7786feaaa26b",
      "download_time": "2025-03-22 15:56:44.892014"
    }
  }
}
```

Where:
- `_meta`: Metadata about the history file
  - `version`: Schema version for future compatibility (integer)
  - `magic`: Fixed identifier string to confirm file type
  - `created`: ISO 8601 formatted timestamp when the history file was created
  - `generator`: Name and version of the program that created this file
- `files`: Dictionary of downloaded files keyed by their file path as it appears in Synology Drive
    - `file_id`: Synology Drive's unique identifier for the file
    - `hash`: hash of the file content provided by Synology NAS for detecting changes
    - `download_time`: ISO 8601 formatted timestamp when the file was last downloaded

The download history is used to implement the incremental download feature, which only downloads files that have been created or modified since the last run.
