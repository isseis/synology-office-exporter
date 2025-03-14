# Synology Office File Downloader

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
git clone https://github.com/isseis/synology-tools.git
cd synology-tools
```

### Install Required Packages

Use the following command to install the required dependencies:

```bash
pip3 install -r requirements/prod.txt
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
python3 main.py [options]
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

### Unable to Install Modules

If you need administrator privileges, use the `--user` flag:

```bash
pip3 install --user -r requirements/prod.txt
```

### Runtime Errors

- `ModuleNotFoundError`: Ensure the required packages are installed correctly.
- Connection errors: Check the NAS IP address and port settings. The default ports are 5000 for HTTP and 5001 for HTTPS.

## License

Copyright (c) 2025 Issei Suzuki

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


## Acknowledgements

- [Synology Drive API](https://github.com/zbjdonald/synology-drive-api) - Used for communication with the Synology Drive API

