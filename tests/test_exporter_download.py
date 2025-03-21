"""Unit tests for the SynologyOfficeExporter download functionality."""
import unittest
from unittest.mock import patch, MagicMock, call
from io import BytesIO
import os
from synology_office_exporter.exporter import SynologyOfficeExporter
from synology_office_exporter.synology_drive_api import SynologyDriveEx


class TestSynologyOfficeExporter(unittest.TestCase):
    """
    Test suite for the SynologyOfficeExporter class.

    This test class covers the main functionality of the SynologyOfficeExporter, including:
    - Processing and downloading Synology Office documents
    - File format conversion (Synology Office to MS Office)
    - Navigation through different storage areas (My Drive, Team Folders, Shared files)
    - Exception handling and error recovery
    - Download history management to avoid redundant downloads
    - Force download option to override history
    """

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter.save_bytesio_to_file')
    def test_process_document(self, mock_save_bytesio_to_file):
        mock_synd = MagicMock(spec=SynologyDriveEx)
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
        mock_synd.download_synology_office_file.return_value = BytesIO(b'test data')

        # Create SynologyOfficeExporter instance with test output directory
        downloader = SynologyOfficeExporter(mock_synd, output_dir='.')
        downloader._process_document('123', 'path/to/test.osheet', hash=None)

        # Check if save_bytesio_to_file was called with correct parameters
        args, kwargs = mock_save_bytesio_to_file.call_args
        self.assertEqual(args[0].getvalue(), b'test data')
        self.assertEqual(os.path.basename(args[1]), 'test.xlsx')

        # Check if download_synology_office_file was called correctly
        mock_synd.download_synology_office_file.assert_called_once_with('123')

    def test_get_offline_name(self):
        # For Synology Office files, convert to MS Office extensions
        self.assertEqual(SynologyOfficeExporter.get_offline_name('test.osheet'), 'test.xlsx')
        self.assertEqual(SynologyOfficeExporter.get_offline_name('test.odoc'), 'test.docx')
        self.assertEqual(SynologyOfficeExporter.get_offline_name('test.oslides'), 'test.pptx')
        # For other files, return None
        self.assertIsNone(SynologyOfficeExporter.get_offline_name('test.txt'))

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter._process_item')
    def test_download_shared_files(self, mock_process_item):
        mock_synd = MagicMock(spec=SynologyDriveEx)
        mock_synd.shared_with_me.return_value = [
            {'file_id': '123', 'content_type': 'document', 'name': 'doc1'},
            {'file_id': '456', 'content_type': 'dir', 'name': 'folder1'}
        ]

        downloader = SynologyOfficeExporter(mock_synd)
        downloader.download_shared_files()

        # Verify _process_item was called for each shared item
        self.assertEqual(mock_process_item.call_count, 2)
        mock_process_item.assert_has_calls([
            call({'file_id': '123', 'content_type': 'document', 'name': 'doc1'}),
            call({'file_id': '456', 'content_type': 'dir', 'name': 'folder1'})
        ])

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter._process_directory')
    def test_download_teamfolder_files(self, mock_process_directory):
        mock_synd = MagicMock(spec=SynologyDriveEx)
        mock_synd.get_teamfolder_info.return_value = {
            'Team Folder 1': '789',
            'Team Folder 2': '012'
        }

        downloader = SynologyOfficeExporter(mock_synd)
        downloader.download_teamfolder_files()

        # Verify _process_directory was called for each team folder
        self.assertEqual(mock_process_directory.call_count, 2)
        mock_process_directory.assert_has_calls([
            call('789', 'Team Folder 1'),
            call('012', 'Team Folder 2')
        ], any_order=True)  # Order of dictionary items is not guaranteed

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter._process_document')
    @patch('synology_office_exporter.exporter.SynologyOfficeExporter._process_directory')
    def test_process_item(self, mock_process_directory, mock_process_document):
        mock_synd = MagicMock(spec=SynologyDriveEx)
        downloader = SynologyOfficeExporter(mock_synd)

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
        # Modify this line to check with positional arguments instead of keyword arguments
        mock_process_document.assert_called_once_with('123', 'path/to/doc.osheet', None)
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

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter._process_directory')
    def test_download_mydrive_files(self, mock_process_directory):
        # Mock SynologyDriveEx
        mock_synd = MagicMock(spec=SynologyDriveEx)

        # Create downloader instance
        downloader = SynologyOfficeExporter(mock_synd)

        # Call method to test
        downloader.download_mydrive_files()

        # Verify _process_directory was called with the correct parameters
        mock_process_directory.assert_called_once_with('/mydrive', 'My Drive')

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter._process_item')
    def test_exception_handling_shared_files(self, mock_process_item):
        """Test that the program continues downloading even if some files cause exceptions."""
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
        downloader = SynologyOfficeExporter(mock_synd)

        # Call method to test
        downloader.download_shared_files()

        # Verify all items were attempted to be processed, despite the exception
        self.assertEqual(mock_process_item.call_count, 3)
        mock_process_item.assert_any_call({'file_id': '123', 'content_type': 'document', 'name': 'doc1'})
        mock_process_item.assert_any_call({'file_id': '456', 'content_type': 'dir', 'name': 'folder1'})
        mock_process_item.assert_any_call({'file_id': '789', 'content_type': 'document', 'name': 'doc2'})

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter._process_directory')
    def test_exception_handling_mydrive(self, mock_process_directory):
        """Test that exceptions in _process_directory do not stop execution."""
        mock_synd = MagicMock(spec=SynologyDriveEx)
        mock_process_directory.side_effect = Exception("Test error")

        downloader = SynologyOfficeExporter(mock_synd)
        downloader.download_mydrive_files()

        # Verify _process_directory was called with correct parameters
        mock_process_directory.assert_called_once_with('/mydrive', 'My Drive')

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter._process_directory')
    def test_exception_handling_teamfolders(self, mock_process_directory):
        """Test that exceptions in one team folder do not prevent processing other folders."""
        mock_synd = MagicMock(spec=SynologyDriveEx)
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

        downloader = SynologyOfficeExporter(mock_synd)
        downloader.download_teamfolder_files()

        # Verify all team folders were attempted to be processed
        self.assertEqual(mock_process_directory.call_count, 3)
        mock_process_directory.assert_any_call('111', 'Team Folder 1')
        mock_process_directory.assert_any_call('222', 'Team Folder 2')
        mock_process_directory.assert_any_call('333', 'Team Folder 3')

    def test_exception_handling_download_synology(self):
        """Test that exceptions during file download do not stop processing."""
        mock_synd = MagicMock(spec=SynologyDriveEx)
        mock_download = MagicMock(side_effect=Exception("Download failed"))

        # Replace the download method in our mock
        mock_synd.download_synology_office_file = mock_download

        downloader = SynologyOfficeExporter(mock_synd)
        downloader.save_bytesio_to_file = MagicMock()
        downloader._process_document('123', 'path/to/test.osheet', hash=None)

        # Verify mocks
        mock_download.assert_called_once_with('123')
        downloader.save_bytesio_to_file.assert_not_called()

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter.save_bytesio_to_file')
    def test_exception_handling_download(self, mock_save):
        """Test that exceptions during file download do not stop processing."""
        mock_synd = MagicMock(spec=SynologyDriveEx)
        mock_synd.download_synology_office_file.side_effect = Exception("Download failed")

        downloader = SynologyOfficeExporter(mock_synd)
        downloader._process_document('123', 'path/to/test.osheet', hash=None)

        # Verify download was attempted
        mock_synd.download_synology_office_file.assert_called_once_with('123')
        # Save should not have been called because download failed
        mock_save.assert_not_called()

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter.save_bytesio_to_file')
    def test_download_history_skips_unchanged_files(self, mock_save):
        """Test that files with unchanged hash are not re-downloaded."""
        mock_synd = MagicMock(spec=SynologyDriveEx)
        mock_synd.download_synology_office_file.return_value = BytesIO(b'test data')

        downloader = SynologyOfficeExporter(mock_synd, output_dir='.')
        downloader.download_history = {
            '123': {
                'hash': 'abc123',
                'path': 'path/to/test.osheet',
                'output_path': './test.xlsx',
                'download_time': '2023-01-01 12:00:00'
            }
        }

        # Process a document that's already in the history with the same hash
        downloader._process_document('123', 'path/to/test.osheet', 'abc123')

        # Verify that download was not attempted
        mock_synd.download_synology_office_file.assert_not_called()
        mock_save.assert_not_called()

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter.save_bytesio_to_file')
    def test_download_history_downloads_changed_files(self, mock_save):
        """Test that files with changed hash are re-downloaded."""
        mock_synd = MagicMock(spec=SynologyDriveEx)
        mock_synd.download_synology_office_file.return_value = BytesIO(b'updated data')

        # Create downloader instance and set up download history with old hash
        downloader = SynologyOfficeExporter(mock_synd, output_dir='.')
        downloader.download_history = {
            '123': {
                'hash': 'old-hash',
                'path': 'path/to/test.osheet',
                'output_path': './test.xlsx',
                'download_time': '2023-01-01 12:00:00'
            }
        }

        # Process a document that's in history but with a new hash
        downloader._process_document('123', 'path/to/test.osheet', 'new-hash')

        # Verify that download was attempted
        mock_synd.download_synology_office_file.assert_called_once_with('123')
        mock_save.assert_called_once()

        # Verify that the history was updated with the new hash
        self.assertEqual(downloader.download_history['123']['hash'], 'new-hash')

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter.save_bytesio_to_file')
    def test_download_history_saves_new_files(self, mock_save):
        """Test that new files are added to download history."""
        mock_synd = MagicMock(spec=SynologyDriveEx)
        mock_synd.download_synology_office_file.return_value = BytesIO(b'new file data')

        downloader = SynologyOfficeExporter(mock_synd, output_dir='.')
        downloader.download_history = {}

        # Process a new document
        downloader._process_document('456', 'path/to/new.osheet', 'new-file-hash')

        # Verify that download was attempted
        mock_synd.download_synology_office_file.assert_called_once_with('456')
        mock_save.assert_called_once()

        # Verify that the new file was added to history
        self.assertIn('456', downloader.download_history)
        self.assertEqual(downloader.download_history['456']['hash'], 'new-file-hash')
        self.assertEqual(downloader.download_history['456']['path'], 'path/to/new.osheet')

    @patch('json.load')
    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    @patch('os.path.exists')
    def test_load_download_history(self, mock_exists, mock_open, mock_json_load):
        """Test that download history is correctly loaded from file."""
        mock_exists.return_value = True
        mock_json_load.return_value = {
            '123': {'hash': 'abc123', 'path': 'test.osheet'},
            '456': {'hash': 'def456', 'path': 'test2.osheet'}
        }

        downloader = SynologyOfficeExporter(MagicMock(), output_dir='/test/dir')

        # _load_download_history is called in __init__, verify it worked
        mock_exists.assert_called_once_with('/test/dir/.download_history.json')
        mock_open.assert_called_once_with('/test/dir/.download_history.json', 'r')
        mock_json_load.assert_called_once()

        # Verify history was loaded correctly
        self.assertEqual(len(downloader.download_history), 2)
        self.assertEqual(downloader.download_history['123']['hash'], 'abc123')

    @patch('json.dump')
    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    @patch('os.makedirs')
    def test_save_download_history(self, mock_makedirs, mock_open, mock_json_dump):
        """Test that download history is correctly saved to file."""
        downloader = SynologyOfficeExporter(MagicMock(), output_dir='/test/dir')
        downloader.download_history = {
            '123': {'hash': 'abc123', 'path': 'test.osheet'},
            '456': {'hash': 'def456', 'path': 'test2.osheet'}
        }

        downloader._save_download_history()

        # Verify file operations
        mock_makedirs.assert_called_once_with('/test/dir', exist_ok=True)
        mock_open.assert_called_once_with('/test/dir/.download_history.json', 'w')
        mock_json_dump.assert_called_once_with(downloader.download_history, mock_open())

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter._process_directory')
    @patch('synology_office_exporter.exporter.SynologyOfficeExporter._save_download_history')
    @patch('synology_office_exporter.exporter.SynologyOfficeExporter._load_download_history')
    def test_context_manager(self, mock_load, mock_save, mock_process):
        """Test that context manager loads and saves download history."""
        mock_synd = MagicMock(spec=SynologyDriveEx)

        with SynologyOfficeExporter(mock_synd, output_dir='/test/dir') as downloader:
            # In the context, _load_download_history should have been called already
            mock_load.assert_called_once()
            mock_save.assert_not_called()  # Not called yet

            # Do something with the downloader
            downloader.download_mydrive_files()

        # After the context, _save_download_history should have been called
        mock_save.assert_called_once()
        mock_process.assert_called_once()

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter.save_bytesio_to_file')
    def test_force_download_ignores_history(self, mock_save):
        """Test that force_download option downloads files regardless of history."""
        mock_synd = MagicMock(spec=SynologyDriveEx)
        mock_synd.download_synology_office_file.return_value = BytesIO(b'test data')

        downloader = SynologyOfficeExporter(mock_synd, output_dir='.', force_download=True)
        downloader.download_history = {
            '123': {
                'hash': 'abc123',
                'path': 'path/to/test.osheet',
                'output_path': './test.xlsx',
                'download_time': '2023-01-01 12:00:00'
            }
        }

        # Process a document that's already in the history with the same hash
        # Even though it's in history with same hash, force_download should cause a redownload
        downloader._process_document('123', 'path/to/test.osheet', 'abc123')

        # Verify that download was attempted despite being in history
        mock_synd.download_synology_office_file.assert_called_once_with('123')
        mock_save.assert_called_once()


if __name__ == '__main__':
    unittest.main()
