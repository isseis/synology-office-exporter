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
                    # Folder should be skipped
                    {'content_type': 'dir', 'encrypted': False, 'name': 'folder',
                     'display_path': 'path/to/folder', 'file_id': '456'},
                    # Office file should be processed
                    {'content_type': 'document', 'encrypted': False, 'name': 'test.osheet',
                     'display_path': 'path/to/test.osheet', 'file_id': '123'},
                    # PDF file shoud be skipped
                    {'content_type': 'document', 'encrypted': False, 'name': 'test.pdf',
                     'display_path': 'path/to/test.pdf', 'file_id': '789'}
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

    @patch('office_file_downloader.OfficeFileDownloader._process_directory')
    def test_download_mydrive_files(self, mock_process_directory):
        # Mock SynologyDriveEx
        mock_synd = MagicMock(spec=SynologyDriveEx)

        # Create downloader instance
        downloader = OfficeFileDownloader(mock_synd)

        # Call method to test
        downloader.download_mydrive_files()

        # Verify _process_directory was called with the correct parameters
        mock_process_directory.assert_called_once_with('/mydrive', 'My Drive')

    @patch('office_file_downloader.OfficeFileDownloader._process_item')
    def test_exception_handling_shared_files(self, mock_process_item):
        """Test that the program continues downloading even if some files cause exceptions."""
        # Mock SynologyDriveEx
        mock_synd = MagicMock(spec=SynologyDriveEx)

        # Set up mock to have 3 files, with processing of the second one raising an exception
        mock_synd.shared_with_me.return_value = [
            {'file_id': '123', 'content_type': 'document', 'name': 'doc1'},
            {'file_id': '456', 'content_type': 'dir', 'name': 'folder1'},
            {'file_id': '789', 'content_type': 'document', 'name': 'doc2'}
        ]

        # Make the second file raise an exception when processed
        def side_effect(item):
            if item['file_id'] == '456':
                raise Exception("Test error")
            return None

        mock_process_item.side_effect = side_effect

        # Create downloader instance
        downloader = OfficeFileDownloader(mock_synd)

        # Call method to test
        downloader.download_shared_files()

        # Verify all items were attempted to be processed, despite the exception
        self.assertEqual(mock_process_item.call_count, 3)
        mock_process_item.assert_any_call({'file_id': '123', 'content_type': 'document', 'name': 'doc1'})
        mock_process_item.assert_any_call({'file_id': '456', 'content_type': 'dir', 'name': 'folder1'})
        mock_process_item.assert_any_call({'file_id': '789', 'content_type': 'document', 'name': 'doc2'})

    @patch('office_file_downloader.OfficeFileDownloader._process_directory')
    def test_exception_handling_mydrive(self, mock_process_directory):
        """Test that exceptions in _process_directory do not stop execution."""
        # Mock SynologyDriveEx
        mock_synd = MagicMock(spec=SynologyDriveEx)

        # Make _process_directory raise an exception
        mock_process_directory.side_effect = Exception("Test error")

        # Create downloader instance
        downloader = OfficeFileDownloader(mock_synd)

        # Call download_mydrive_files - this should not raise an exception
        downloader.download_mydrive_files()

        # Verify _process_directory was called with correct parameters
        mock_process_directory.assert_called_once_with('/mydrive', 'My Drive')

    @patch('office_file_downloader.OfficeFileDownloader._process_directory')
    def test_exception_handling_teamfolders(self, mock_process_directory):
        """Test that exceptions in one team folder do not prevent processing other folders."""
        # Mock SynologyDriveEx
        mock_synd = MagicMock(spec=SynologyDriveEx)

        # Mock get_teamfolder_info response
        mock_synd.get_teamfolder_info.return_value = {
            'Team Folder 1': '111',
            'Team Folder 2': '222',
            'Team Folder 3': '333'
        }

        # Make processing of 'Team Folder 2' raise an exception
        def side_effect(file_id, name):
            if file_id == '222':
                raise Exception("Test error")
            return None

        mock_process_directory.side_effect = side_effect

        # Create downloader instance
        downloader = OfficeFileDownloader(mock_synd)

        # Call method to test
        downloader.download_teamfolder_files()

        # Verify all team folders were attempted to be processed
        self.assertEqual(mock_process_directory.call_count, 3)
        mock_process_directory.assert_any_call('111', 'Team Folder 1')
        mock_process_directory.assert_any_call('222', 'Team Folder 2')
        mock_process_directory.assert_any_call('333', 'Team Folder 3')

    @patch('office_file_downloader.SynologyDriveEx.download_synology_office_file')
    @patch('office_file_downloader.OfficeFileDownloader.save_bytesio_to_file')
    def test_exception_handling_download(self, mock_save, mock_download):
        """Test that exceptions during file download do not stop processing."""
        # Mock SynologyDriveEx
        mock_synd = MagicMock(spec=SynologyDriveEx)

        # Mock download to raise an exception
        mock_download.side_effect = Exception("Download failed")

        # Create downloader instance and test document
        downloader = OfficeFileDownloader(mock_synd)

        # This should not raise an exception out of the method
        downloader._process_document('123', 'path/to/test.osheet')

        # Verify download was attempted
        mock_download.assert_called_once_with('123')
        # Save should not have been called because download failed
        mock_save.assert_not_called()

    @patch('office_file_downloader.OfficeFileDownloader.save_bytesio_to_file')
    def test_exception_handling_download(self, mock_save):
        """Test that exceptions during file download do not stop processing."""
        # Mock SynologyDriveEx
        mock_synd = MagicMock(spec=SynologyDriveEx)

        # Mock download_synology_office_file to raise an exception
        mock_synd.download_synology_office_file.side_effect = Exception("Download failed")

        # Create downloader instance and test document
        downloader = OfficeFileDownloader(mock_synd)

        # This should not raise an exception out of the method
        downloader._process_document('123', 'path/to/test.osheet')

        # Verify download was attempted
        mock_synd.download_synology_office_file.assert_called_once_with('123')
        # Save should not have been called because download failed
        mock_save.assert_not_called()


if __name__ == '__main__':
    unittest.main()
