#! /usr/bin/python3

from io import BytesIO
import os
import sys
from typing import Optional

from dotenv import load_dotenv
from synology_drive_ex import SynologyDriveEx


# BytesIO オブジェクトの内容をファイルに書き込む
def save_bytesio_to_file(data: BytesIO, filename: str):
    # ポインタを先頭に戻す
    data.seek(0)

    # バイナリモードでファイルを開いて書き込む
    with open(filename, 'wb') as f:
        f.write(data.getvalue())


class OfficeFileFetcher:
    def __init__(self, synd: SynologyDriveEx):
        self.synd = synd

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def execute(self, owner_name: str, dir_name: str, file_id: str):
        # print(owner_name, dir_name, file_id)
        resp = self.synd.list_folder(file_id)
        if not resp['success']:
            raise Exception('list folder failed.')
        for item in resp['data']['items']:
            if item['content_type'] == 'dir':
                pass
            if item['content_type'] != 'document' or item['encrypted']:
                continue
            offline_name = self.get_offline_name(item['name'])
            if not offline_name:
                continue
            display_path = item['display_path']
            print(f'{display_path} => {owner_name}_{dir_name}_{offline_name}')
            data = self.synd.download_synology_office_file(item['file_id'])
            save_bytesio_to_file(data, f'{owner_name}_{dir_name}_{offline_name}')

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
    # .envファイルの読み込み
    load_dotenv()

    NAS_USER = os.getenv('SYNOLOGY_NAS_USER')
    NAS_PASS = os.getenv('SYNOLOGY_NAS_PASS')
    NAS_IP = os.getenv('SYNOLOGY_NAS_IP')

    # default http port is 5000, https is 5001.
    with SynologyDriveEx(NAS_USER, NAS_PASS, NAS_IP, dsm_version='7') as synd:
        for item in synd.shared_with_me():
            owner_name = item['owner']['name']
            dir_name = item['name']
            file_id = item['file_id']
            with OfficeFileFetcher(synd) as off:
                off.execute(owner_name, dir_name, file_id)

        # print(synd.list_folder('871932547865555615'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
