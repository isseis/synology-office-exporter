import unittest
from unittest.mock import patch, MagicMock
from io import BytesIO
from drive_export import OfficeFileFetcher, SynologyDriveEx


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

        # Create OfficeFileFetcher instance
        fetcher = OfficeFileFetcher(mock_synd)

        # Execute with test data
        fetcher._process('owner', 'dir', 'file_id')

        # Check if save_bytesio_to_file was called with correct parameters
        args, kwargs = mock_save_bytesio_to_file.call_args
        self.assertEqual(args[0].getvalue(), b'test data')
        self.assertEqual(args[1], 'owner_dir_test.xlsx')

        # Check if list_folder and download_synology_office_file were called correctly
        mock_synd.list_folder.assert_called_once_with('file_id')
        mock_synd.download_synology_office_file.assert_called_once_with('123')

    def test_get_offline_name(self):
        # Synology office のファイルの場合 MS Office 拡張子に変換する。
        self.assertEqual(OfficeFileFetcher.get_offline_name('test.osheet'), 'test.xlsx')
        self.assertEqual(OfficeFileFetcher.get_offline_name('test.odoc'), 'test.docx')
        self.assertEqual(OfficeFileFetcher.get_offline_name('test.oslides'), 'test.pptx')
        # それ以外の場合は None を返す。
        self.assertIsNone(OfficeFileFetcher.get_offline_name('test.txt'))


if __name__ == '__main__':
    unittest.main()
