# Synology Office Exporter
![Python](https://img.shields.io/badge/python-v3.6+-blue.svg)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://opensource.org/licenses/MIT)
![Contributions welcome](https://img.shields.io/badge/contributions-welcome-orange.svg)
[![Python App](https://github.com/isseis/synology-office-exporter/actions/workflows/python-app.yml/badge.svg)](https://github.com/isseis/synology-office-exporter/actions/workflows/python-app.yml)

This tool downloads Synology Office files from your Synology NAS and converts them to Microsoft Office formats. It processes Synology Office documents from your personal My Drive, team folders, and shared files, converting them to their corresponding Microsoft Office formats.

## File Conversion Types

- Synology Spreadsheet (`.osheet`) → Microsoft Excel (`.xlsx`)
- Synology Document (`.odoc`) → Microsoft Word (`.docx`)
- Synology Slides (`.oslides`) → Microsoft PowerPoint (`.pptx`)

## Requirements

- Python 3.6+

## Installation

```bash
pip install synology-office-exporter
```

After installation, you can run the tool using the command:

```bash
synology-office-exporter --help
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

## Features

- Connects to Synology NAS and downloads Synology Office files from My Drive, team folders, and shared files
- Saves files to the specified output directory while preserving directory structure
- Tracks download history to avoid re-downloading unchanged files (can be overridden with the `--force` option)
- Automatically skips encrypted files (as they cannot be converted automatically)

## Notes

- This tool uses the Synology Drive API to access files.
- If you have a large number of files, the initial run may take some time.
- Subsequent runs will only download changed files (unless the `--force` option is used).

## Security Considerations

When using this tool, please be aware of the following security aspects:

- **Credentials Storage**: The `.env` file contains sensitive login credentials. Make sure to:
  - Never commit this file to version control systems
  - Set restrictive file permissions (e.g., `chmod 600 .env`)
  - Store it only in secure locations

- **Command Line Security**: Using credentials as command line arguments may expose them in your shell history or process listings. Prefer using the `.env` file or interactive prompt when possible.

- **Network Security**: When connecting to your Synology NAS over the internet, ensure you're using a secure connection (HTTPS). Consider using a VPN if accessing your NAS remotely.

- **Output Files**: Downloaded files inherit the permissions of the process running the tool. Be mindful of who has access to the output directory.

## Troubleshooting

### Runtime Errors

- `ModuleNotFoundError`: Ensure the required packages are installed correctly.
- Connection errors: Check the NAS IP address and port settings. The default ports are 5000 for HTTP and 5001 for HTTPS.

## Development

For developers interested in contributing to this project, please see the [DEVELOPMENT.md](DEVELOPMENT.md) file for detailed instructions on setting up the development environment, running tests, and contributing code.

## Acknowledgements

- [Synology Drive API](https://github.com/zbjdonald/synology-drive-api) - Used for communication with the Synology Drive API
