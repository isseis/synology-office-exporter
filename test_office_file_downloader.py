import unittest
from unittest.mock import patch, MagicMock, call
from io import BytesIO
import os
from office_file_downloader import OfficeFileDownloader, SynologyDriveEx


class TestOfficeFileDownloader(unittest.TestCase):
    @patch('office_file_downloader.OfficeFileDownloader.save_bytesio_to_file')
    def test_process_document(self, mock_save_bytesio_to_file):
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
        downloader = OfficeFileDownloader(mock_synd, output_dir='.')
        downloader._process_document('123', 'path/to/test.osheet')

        # Check if save_bytesio_to_file was called with correct parameters
        args, kwargs = mock_save_bytesio_to_file.call_args
        self.assertEqual(args[0].getvalue(), b'test data')
        self.assertEqual(os.path.basename(args[1]), 'test.xlsx')

        # Check if download_synology_office_file was called correctly
        mock_synd.download_synology_office_file.assert_called_once_with('123')

    def test_get_offline_name(self):
        # For Synology Office files, convert to MS Office extensions
        self.assertEqual(OfficeFileDownloader.get_offline_name('test.osheet'), 'test.xlsx')
        self.assertEqual(OfficeFileDownloader.get_offline_name('test.odoc'), 'test.docx')
        self.assertEqual(OfficeFileDownloader.get_offline_name('test.oslides'), 'test.pptx')
        # For other files, return None
        self.assertIsNone(OfficeFileDownloader.get_offline_name('test.txt'))

    @patch('office_file_downloader.OfficeFileDownloader._process_item')
    def test_download_shared_files(self, mock_process_item):
        # Mock SynologyDriveEx
        mock_synd = MagicMock(spec=SynologyDriveEx)

        # Mock shared_with_me response
        mock_synd.shared_with_me.return_value = [
            {'file_id': '123', 'content_type': 'document', 'name': 'doc1'},
            {'file_id': '456', 'content_type': 'dir', 'name': 'folder1'}
        ]

        # Create downloader instance
        downloader = OfficeFileDownloader(mock_synd)

        # Call method to test
        downloader.download_shared_files()

        # Verify _process_item was called for each shared item
        self.assertEqual(mock_process_item.call_count, 2)
        mock_process_item.assert_has_calls([
            call({'file_id': '123', 'content_type': 'document', 'name': 'doc1'}),
            call({'file_id': '456', 'content_type': 'dir', 'name': 'folder1'})
        ])

    @patch('office_file_downloader.OfficeFileDownloader._process_directory')
    def test_download_teamfolder_files(self, mock_process_directory):
        # Mock SynologyDriveEx
        mock_synd = MagicMock(spec=SynologyDriveEx)

        # Mock get_teamfolder_info response
        mock_synd.get_teamfolder_info.return_value = {
            'Team Folder 1': '789',
            'Team Folder 2': '012'
        }

        # Create downloader instance
        downloader = OfficeFileDownloader(mock_synd)

        # Call method to test
        downloader.download_teamfolder_files()

        # Verify _process_directory was called for each team folder
        self.assertEqual(mock_process_directory.call_count, 2)
        mock_process_directory.assert_has_calls([
            call('789', 'Team Folder 1'),
            call('012', 'Team Folder 2')
        ], any_order=True)  # Order of dictionary items is not guaranteed

    @patch('office_file_downloader.OfficeFileDownloader._process_document')
    @patch('office_file_downloader.OfficeFileDownloader._process_directory')
    def test_process_item(self, mock_process_directory, mock_process_document):
        # Mock SynologyDriveEx
        mock_synd = MagicMock(spec=SynologyDriveEx)

        # Create downloader instance
        downloader = OfficeFileDownloader(mock_synd)

        # Test directory item
        dir_item = {
            'file_id': '456',
            'content_type': 'dir',
            'display_path': 'path/to/folder'
        }
        downloader._process_item(dir_item)
        mock_process_directory.assert_called_once_with('456', 'path/to/folder')
        mock_process_document.assert_not_called()

        # Reset mocks
        mock_process_directory.reset_mock()
        mock_process_document.reset_mock()

        # Test document item
        doc_item = {
            'file_id': '123',
            'content_type': 'document',
            'display_path': 'path/to/doc.osheet',
            'encrypted': False
        }
        downloader._process_item(doc_item)
        mock_process_document.assert_called_once_with('123', 'path/to/doc.osheet')
        mock_process_directory.assert_not_called()

        # Reset mocks
        mock_process_directory.reset_mock()
        mock_process_document.reset_mock()

        # Test encrypted document item
        encrypted_doc = {
            'file_id': '789',
            'content_type': 'document',
            'display_path': 'path/to/secret.osheet',
            'encrypted': True
        }
        downloader._process_item(encrypted_doc)
        mock_process_document.assert_not_called()
        mock_process_directory.assert_not_called()


if __name__ == '__main__':
    unittest.main()
