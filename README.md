# Synology Office Exporter
![Python](https://img.shields.io/badge/python-v3.6+-blue.svg)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://opensource.org/licenses/MIT)
![Contributions welcome](https://img.shields.io/badge/contributions-welcome-orange.svg)

This tool downloads Synology Office files from your Synology NAS and converts them to Microsoft Office formats. It processes Synology Office documents from your personal My Drive, team folders, and shared files, converting them to their corresponding Microsoft Office formats.

## File Conversion Types

- Synology Spreadsheet (`.osheet`) → Microsoft Excel (`.xlsx`)
- Synology Document (`.odoc`) → Microsoft Word (`.docx`)
- Synology Slides (`.oslides`) → Microsoft PowerPoint (`.pptx`)

## Requirements

- Python 3.6+
- synology-drive-api package
- python-dotenv package

## Installation

### Clone the Repository

```bash
git clone https://github.com/isseis/synology-office-exporter.git
cd synology-office-exporter
```

### Create virtual environment
It's recommended to create Python virtual environment and run the tools inside it.

For bash / zsh users:
```bash
python -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
```

#### Mac users

In case you encounter error message like `zsh: command not found: python`, you should run `python3 -m venv .venv` instead of `python -m venv .venv` in the commands above.

### Using pyproject.toml

The project includes a `pyproject.toml` file for modern Python packaging. You can:

#### Build and install the package

```bash
pip install .
```

After installation, you can run the tool using the command:

```bash
synology-office-exporter --help
```

## Development

You may skip this section if you just want to use this tool.

### Install development packages

```bash
pip install -e '.[dev]'
```

This installs packages used for development, and install this project in editable mode.

### Setting up pre-commit hooks

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

### Linting

To check code style with flake8:

```bash
make lint
```

or

```bash
flake8 --config .flake8
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

## Configuration

Create a `.env` file and set the following environment variables:

```
SYNOLOGY_NAS_USER=your_username
SYNOLOGY_NAS_PASS=your_password
SYNOLOGY_NAS_HOST=your_nas_ip_or_hostname
```

## Usage

### Command Line

```bash
python -m synology_office_exporter.main [options]
```

Or if installed:

```bash
synology-office-exporter [options]
```

### Options

- `-o, --output DIR` - Directory to save files (default: current directory)
- `-u, --username USER` - Synology username
- `-p, --password PASS` - Synology password
- `-s, --server HOST` - Synology server URL
- `-f, --force` - Force download all files, ignoring download history
- `--log-level LEVEL` - Set log level (default: info)
  - Choices: debug, info, warning, error, critical
- `-h, --help` - Show help message

### Authentication

Authentication can be provided in three ways (in order of priority):

1. Command line arguments (-u, -p, -s)
2. Environment variables (via .env file: SYNOLOGY_NAS_USER, SYNOLOGY_NAS_PASS, SYNOLOGY_NAS_HOST)
3. Interactive prompt

### Using Makefile

```bash
make run ARGS="-f --log-level debug"
```

By default, files are saved in the `out` directory (specified in the Makefile).

## Features

- Connects to Synology NAS and downloads Synology Office files from My Drive, team folders, and shared files
- Saves files to the specified output directory while preserving directory structure
- Tracks download history to avoid re-downloading unchanged files (can be overridden with the `--force` option)
- Automatically skips encrypted files (as they cannot be converted automatically)

## Notes

- This tool uses the Synology Drive API to access files.
- If you have a large number of files, the initial run may take some time.
- Subsequent runs will only download changed files (unless the `--force` option is used).

## Troubleshooting

### Runtime Errors

- `ModuleNotFoundError`: Ensure the required packages are installed correctly.
- Connection errors: Check the NAS IP address and port settings. The default ports are 5000 for HTTP and 5001 for HTTPS.
- `SSL: CERTIFICATE_VERIFY_FAILED`: Ensure the NAS has a valid SSL certificate or use the `--no-verify` option to skip SSL verification.

## Acknowledgements

- [Synology Drive API](https://github.com/zbjdonald/synology-drive-api) - Used for communication with the Synology Drive API
