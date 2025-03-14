import unittest
from unittest.mock import patch, MagicMock
from io import BytesIO
import os
from drive_export import OfficeFileDownloader, SynologyDriveEx


class TestOfficeFileFetcher(unittest.TestCase):
    @patch('drive_export.save_bytesio_to_file')
    def test_execute(self, mock_save_bytesio_to_file):
        # Mock SynologyDriveEx
        mock_synd = MagicMock(spec=SynologyDriveEx)

        # Mock list_folder response
        mock_synd.list_folder.return_value = {
            'success': True,
            'data': {
                'items': [
                    {'content_type': 'document', 'encrypted': False, 'name': 'test.osheet',
                     'display_path': 'path/to/test.osheet', 'file_id': '123'},
                    {'content_type': 'dir', 'encrypted': False, 'name': 'folder',
                     'display_path': 'path/to/folder', 'file_id': '456'}
                ]
            }
        }

        # Mock download_synology_office_file response
        mock_synd.download_synology_office_file.return_value = BytesIO(b'test data')

        # Create OfficeFileDownloader instance with test output directory
        fetcher = OfficeFileDownloader(mock_synd, output_dir='.')

        # Call _process_document directly instead of nonexistent _process method
        fetcher._process_document('123', 'path/to/test.osheet')

        # Check if save_bytesio_to_file was called with correct parameters
        args, kwargs = mock_save_bytesio_to_file.call_args
        self.assertEqual(args[0].getvalue(), b'test data')
        self.assertEqual(os.path.basename(args[1]), 'path_to_test.xlsx')

        # Check if download_synology_office_file was called correctly
        mock_synd.download_synology_office_file.assert_called_once_with('123')

    def test_get_offline_name(self):
        # Synology office のファイルの場合 MS Office 拡張子に変換する。
        self.assertEqual(OfficeFileDownloader.get_offline_name('test.osheet'), 'test.xlsx')
        self.assertEqual(OfficeFileDownloader.get_offline_name('test.odoc'), 'test.docx')
        self.assertEqual(OfficeFileDownloader.get_offline_name('test.oslides'), 'test.pptx')
        # それ以外の場合は None を返す。
        self.assertIsNone(OfficeFileDownloader.get_offline_name('test.txt'))


if __name__ == '__main__':
    unittest.main()
