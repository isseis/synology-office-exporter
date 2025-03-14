#! /usr/bin/python3

from io import BytesIO
import logging
import os
import sys
import argparse
from typing import Optional

from dotenv import load_dotenv
from synology_drive_ex import SynologyDriveEx

# Mapping of log level strings to actual log levels
LOG_LEVELS = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL
}


# Write the contents of a BytesIO object to a file
def save_bytesio_to_file(data: BytesIO, filename: str):
    # Reset pointer to the beginning
    data.seek(0)

    # Open file in binary mode and write data
    with open(filename, 'wb') as f:
        f.write(data.getvalue())


class OfficeFileFetcher:
    def __init__(self, synd: SynologyDriveEx):
        self.synd = synd

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def execute(self, file_id: str):
        resp = self.synd.list_folder(file_id)
        if not resp['success']:
            raise Exception('list folder failed.')
        for item in resp['data']['items']:
            file_id = item['file_id']
            display_path = item['display_path']
            content_type = item['content_type']

            if content_type == 'dir':
                self._process_directory(file_id, display_path)
            elif content_type == 'document':
                logging.debug(f'Processing {display_path}')
                if item['encrypted']:
                    logging.info(f'Skipping encrypted file: {display_path}')
                self._process_document(file_id, display_path)

    def _process_directory(self, file_id: str, display_path: str):
        logging.info(f'Processing directory: {display_path}')
        # TODO: Implement directory handling
        pass

    def _process_document(self, file_id: str, display_path: str):
        offline_name = self.get_offline_name(display_path)
        if not offline_name:
            logging.info(f'Skipping non-Synology Office file: {display_path}')
            return

        logging.info(f'Downloading {display_path} => {offline_name}')
        data = self.synd.download_synology_office_file(file_id)
        save_bytesio_to_file(data, offline_name.replace('/', '_'))

    @staticmethod
    def get_offline_name(name: str) -> Optional[str]:
        """
        Converts Synology Office file names to Microsoft Office file names.

        File type conversions:
        - osheet -> xlsx (Excel)
        - odoc -> docx (Word)
        - oslides -> pptx (PowerPoint)

        Parameters:
            name (str): The file name to convert

        Returns:
            str or None: The file name with corresponding Microsoft Office extension.
                        Returns None if not a Synology Office file.
        """
        extension_mapping = {
            '.osheet': '.xlsx',
            '.odoc': '.docx',
            '.oslides': '.pptx'
        }
        for ext, new_ext in extension_mapping.items():
            if name.endswith(ext):
                return name[: -len(ext)] + new_ext
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description='Tool to export Synology Office files')
    parser.add_argument(
        '--log-level',
        default='info',
        choices=LOG_LEVELS.keys(),
        help='Set the logging level (default: info)'
    )
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=LOG_LEVELS[args.log_level],
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Load .env file
    load_dotenv()
    nas_user = os.getenv('SYNOLOGY_NAS_USER')
    nas_pass = os.getenv('SYNOLOGY_NAS_PASS')
    nas_host = os.getenv('SYNOLOGY_NAS_HOST')

    # Check if all required environment variables are set
    missing = [var for var, val in [('SYNOLOGY_NAS_USER', nas_user),
                                    ('SYNOLOGY_NAS_PASS', nas_pass),
                                    ('SYNOLOGY_NAS_HOST', nas_host)] if not val]
    if missing:
        logging.error(f"Environment variables not set: {', '.join(missing)}")
        logging.error("Please set the following variables in your .env file and try again:")
        for var in missing:
            logging.error(f"  {var}=value")
        return 1

    # default http port is 5000, https is 5001.
    with SynologyDriveEx(nas_user, nas_pass, nas_host, dsm_version='7') as synd:
        for item in synd.shared_with_me():
            file_id = item['file_id']
            with OfficeFileFetcher(synd) as off:
                off.execute(file_id)

        # print(synd.list_folder('871932547865555615'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
