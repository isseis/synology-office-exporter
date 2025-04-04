"""Unit tests for the SynologyOfficeExporter download functionality."""
import json
import unittest
from unittest.mock import patch, MagicMock, call
from io import BytesIO
import os
from synology_office_exporter.download_history import HISTORY_MAGIC
from synology_office_exporter.exporter import SynologyOfficeExporter
from synology_office_exporter.synology_drive_api import SynologyDriveEx
from tests.mock_download_history import MockDownloadHistory


class TestDownload(unittest.TestCase):
    """Test suite for the SynologyOfficeExporter download functionality."""

    def setUp(self):
        self.mock_synd = MagicMock(spec=SynologyDriveEx)

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter.save_bytesio_to_file')
    def test_process_document(self, mock_save_bytesio_to_file):
        self.mock_synd.list_folder.return_value = {
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
        self.mock_synd.download_synology_office_file.return_value = BytesIO(b'test data')

        # Create SynologyOfficeExporter instance with test output directory
        exporter = SynologyOfficeExporter(self.mock_synd, download_history_storage=MagicMock())
        exporter.save_bytesio_to_file = mock_save_bytesio_to_file
        exporter._process_document('123', 'path/to/test.osheet', hash=None)

        # Check if save_bytesio_to_file was called with correct parameters
        args, kwargs = mock_save_bytesio_to_file.call_args
        self.assertEqual(args[0].getvalue(), b'test data')
        self.assertEqual(os.path.basename(args[1]), 'test.xlsx')

        # Check if download_synology_office_file was called correctly
        self.mock_synd.download_synology_office_file.assert_called_once_with('123')

    def test_convert_synology_to_ms_office_filename(self):
        # For Synology Office files, convert to MS Office extensions
        self.assertEqual(SynologyOfficeExporter.convert_synology_to_ms_office_filename('test.osheet'), 'test.xlsx')
        self.assertEqual(SynologyOfficeExporter.convert_synology_to_ms_office_filename('test.odoc'), 'test.docx')
        self.assertEqual(SynologyOfficeExporter.convert_synology_to_ms_office_filename('test.oslides'), 'test.pptx')
        # For other files, return None
        self.assertIsNone(SynologyOfficeExporter.convert_synology_to_ms_office_filename('test.txt'))

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter._process_item')
    def test_download_shared_files(self, mock_process_item):
        self.mock_synd.shared_with_me.return_value = [
            {'file_id': '123', 'content_type': 'document', 'name': 'doc1'},
            {'file_id': '456', 'content_type': 'dir', 'name': 'folder1'}
        ]

        exporter = SynologyOfficeExporter(self.mock_synd, download_history_storage=MagicMock())
        exporter.download_shared_files()

        # Verify _process_item was called for each shared item
        self.assertEqual(mock_process_item.call_count, 2)
        mock_process_item.assert_has_calls([
            call({'file_id': '123', 'content_type': 'document', 'name': 'doc1'}),
            call({'file_id': '456', 'content_type': 'dir', 'name': 'folder1'})
        ])

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter._process_directory')
    def test_download_teamfolder_files(self, mock_process_directory):
        self.mock_synd.get_teamfolder_info.return_value = {
            'Team Folder 1': '789',
            'Team Folder 2': '012'
        }

        exporter = SynologyOfficeExporter(self.mock_synd, download_history_storage=MagicMock())
        exporter.download_teamfolder_files()

        # Verify _process_directory was called for each team folder
        self.assertEqual(mock_process_directory.call_count, 2)
        mock_process_directory.assert_has_calls([
            call('789', 'Team Folder 1'),
            call('012', 'Team Folder 2')
        ], any_order=True)  # Order of dictionary items is not guaranteed

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter._process_document')
    @patch('synology_office_exporter.exporter.SynologyOfficeExporter._process_directory')
    def test_process_item(self, mock_process_directory, mock_process_document):
        exporter = SynologyOfficeExporter(self.mock_synd, download_history_storage=MagicMock())

        # Test directory item
        dir_item = {
            'file_id': '456',
            'content_type': 'dir',
            'display_path': 'path/to/folder'
        }
        exporter._process_item(dir_item)
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
        exporter._process_item(doc_item)
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
        exporter._process_item(encrypted_doc)
        mock_process_document.assert_not_called()
        mock_process_directory.assert_not_called()

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter._process_directory')
    def test_download_mydrive_files(self, mock_process_directory):
        exporter = SynologyOfficeExporter(self.mock_synd, download_history_storage=MagicMock)

        exporter.download_mydrive_files()
        mock_process_directory.assert_called_once_with('/mydrive', 'My Drive')

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter._process_item')
    def test_exception_handling_shared_files(self, mock_process_item):
        """Test that the program continues downloading even if some files cause exceptions."""
        # Set up mock to have 3 files, with processing of the second one raising an exception
        self.mock_synd.shared_with_me.return_value = [
            {'file_id': '123', 'content_type': 'document', 'name': 'doc1'},
            {'file_id': '456', 'content_type': 'dir', 'name': 'folder1'},
            {'file_id': '789', 'content_type': 'document', 'name': 'doc2'}
        ]

        # Make the second file raise an exception when processed
        def side_effect(item):
            if item['file_id'] == '456':
                raise Exception('Test error')
            return None
        mock_process_item.side_effect = side_effect

        # Create exporter instance
        exporter = SynologyOfficeExporter(self.mock_synd, download_history_storage=MagicMock())

        # Call method to test
        exporter.download_shared_files()

        # Verify all items were attempted to be processed, despite the exception
        self.assertEqual(mock_process_item.call_count, 3)
        mock_process_item.assert_any_call({'file_id': '123', 'content_type': 'document', 'name': 'doc1'})
        mock_process_item.assert_any_call({'file_id': '456', 'content_type': 'dir', 'name': 'folder1'})
        mock_process_item.assert_any_call({'file_id': '789', 'content_type': 'document', 'name': 'doc2'})

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter._process_directory')
    def test_exception_handling_mydrive(self, mock_process_directory):
        """Test that exceptions in _process_directory do not stop execution."""
        mock_process_directory.side_effect = Exception('Test error')

        exporter = SynologyOfficeExporter(self.mock_synd, download_history_storage=MagicMock())
        exporter.download_mydrive_files()

        # Verify _process_directory was called with correct parameters
        mock_process_directory.assert_called_once_with('/mydrive', 'My Drive')

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter._process_directory')
    def test_exception_handling_teamfolders(self, mock_process_directory):
        """Test that exceptions in one team folder do not prevent processing other folders."""
        self.mock_synd.get_teamfolder_info.return_value = {
            'Team Folder 1': '111',
            'Team Folder 2': '222',
            'Team Folder 3': '333'
        }

        # Make processing of 'Team Folder 2' raise an exception
        def side_effect(file_id, name):
            if file_id == '222':
                raise Exception('Test error')
            return None
        mock_process_directory.side_effect = side_effect

        exporter = SynologyOfficeExporter(self.mock_synd, download_history_storage=MagicMock())
        exporter.download_teamfolder_files()

        # Verify all team folders were attempted to be processed
        self.assertEqual(mock_process_directory.call_count, 3)
        mock_process_directory.assert_any_call('111', 'Team Folder 1')
        mock_process_directory.assert_any_call('222', 'Team Folder 2')
        mock_process_directory.assert_any_call('333', 'Team Folder 3')

    @patch('synology_drive_api.drive.SynologyDrive.download_synology_office_file')
    @patch('synology_office_exporter.exporter.SynologyOfficeExporter.save_bytesio_to_file')
    def test_exception_handling_download_synology(self, mock_save, mock_download):
        """Test that exceptions during file download do not stop processing."""
        mock_download.side_effect = Exception('Download failed')
        self.mock_synd.download_synology_office_file = mock_download

        exporter = SynologyOfficeExporter(self.mock_synd, download_history_storage=MagicMock())
        exporter._process_document('123', 'path/to/test.osheet', hash=None)

        mock_download.assert_called_once_with('123')
        mock_save.assert_not_called()

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter.save_bytesio_to_file')
    def test_exception_handling_download(self, mock_save):
        """Test that exceptions during file download do not stop processing."""
        self.mock_synd.download_synology_office_file.side_effect = Exception('Download failed')

        exporter = SynologyOfficeExporter(self.mock_synd, download_history_storage=MagicMock())
        exporter._process_document('123', 'path/to/test.osheet', hash=None)

        # Verify download was attempted
        self.mock_synd.download_synology_office_file.assert_called_once_with('123')
        # Save should not have been called because download failed
        mock_save.assert_not_called()

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter.save_bytesio_to_file')
    def test_download_history_skips_should_not_download_files(self, mock_save):
        """Test that files with unchanged hash are not re-downloaded."""
        self.mock_synd.download_synology_office_file.return_value = BytesIO(b'test data')

        download_history = MagicMock()
        download_history.should_download.return_value = False

        with SynologyOfficeExporter(self.mock_synd,
                                    download_history_storage=download_history) as exporter:
            exporter._process_document('123', 'path/to/test.osheet', 'old-hash')

        # Verify that download was not attempted
        self.mock_synd.download_synology_office_file.assert_not_called()
        mock_save.assert_not_called()

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter.save_bytesio_to_file')
    def test_download_history_saves_files(self, mock_save):
        """Test that new files are added to download history."""
        self.mock_synd.download_synology_office_file.return_value = BytesIO(b'new file data')
        download_history = MagicMock()
        with SynologyOfficeExporter(self.mock_synd, download_history_storage=download_history) as exporter:
            exporter._process_document('456', 'path/to/new.osheet', 'new-file-hash')

        # Verify that download was attempted
        self.mock_synd.download_synology_office_file.assert_called_once_with('456')
        mock_save.assert_called_once()
        download_history.add_history_entry.assert_called_once_with(
            'path/to/new.osheet', '456', 'new-file-hash')

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter.save_bytesio_to_file')
    def test_load_download_history(self, mock_save):
        """Test that custom download history storage is properly used."""
        # Create the mock download history instance
        download_history = MockDownloadHistory()

        # Use the custom history storage with the exporter
        with SynologyOfficeExporter(self.mock_synd, output_dir='/test/dir',
                                    download_history_storage=download_history) as exporter:
            # Verify that the exporter is using our custom history storage

            # Verify that lock and load methods were called during initialization
            self.assertTrue(download_history.lock_called)
            self.assertTrue(download_history.load_called)
            self.assertFalse(download_history.save_called)  # Not called yet
            self.assertFalse(download_history.unlock_called)  # Not called yet

            # Simulate a file processing operation to test other methods
            dummy_doc = {'file_id': '123', 'display_path': 'test.osheet',
                         'content_type': 'document', 'encrypted': False}
            exporter._process_item(dummy_doc)

            # Check if appropriate history methods were called
            self.assertTrue(download_history.should_download_called)

            # Mock a download and update to history
            self.assertTrue(download_history.add_history_called)

        # Check that save and unlock were called when exiting the context
        self.assertTrue(download_history.save_called)
        self.assertTrue(download_history.unlock_called)

    @patch('synology_office_exporter.exporter.DownloadHistoryFile.unlock_history')
    @patch('synology_office_exporter.exporter.DownloadHistoryFile.lock_history')
    @patch('synology_office_exporter.exporter.DownloadHistoryFile.save_history')
    @patch('synology_office_exporter.exporter.DownloadHistoryFile.load_history')
    @patch('synology_office_exporter.exporter.SynologyOfficeExporter._process_directory')
    def test_context_manager(self, mock_process, mock_load, mock_save, mock_lock, mock_unlock):
        """Test that context manager loads and saves download history."""
        with SynologyOfficeExporter(self.mock_synd, output_dir='/test/dir') as exporter:
            # In the context, _load_download_history should have been called already
            mock_load.assert_called_once()
            mock_save.assert_not_called()  # Not called yet
            mock_lock.assert_called_once()
            mock_unlock.assert_not_called()

        # Do something with the exporter
        exporter.download_mydrive_files()

        # After the context, _save_download_history should have been called
        mock_save.assert_called_once()
        mock_process.assert_called_once()
        mock_unlock.assert_called_once()

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter.save_bytesio_to_file')
    def test_force_download_ignores_history(self, mock_save):
        """Test that force_download option downloads files regardless of history."""
        self.mock_synd.download_synology_office_file.return_value = BytesIO(b'test data')

        exporter = SynologyOfficeExporter(self.mock_synd, output_dir='.',
                                          force_download=True, download_history_storage=MagicMock())
        exporter.download_history = {
            'path/to/test.osheet': {
                'file_id': '123',
                'hash': 'abc123',
                'path': 'path/to/test.osheet',
                'download_time': '2023-01-01 12:00:00'
            }
        }

        # Process a document that's already in the history with the same hash
        # Even though it's in history with same hash, force_download should cause a redownload
        exporter._process_document('123', 'path/to/test.osheet', 'abc123')

        # Verify that download was attempted despite being in history
        self.mock_synd.download_synology_office_file.assert_called_once_with('123')
        mock_save.assert_called_once()

    @patch('synology_office_exporter.exporter.DownloadHistoryFile.lock_history')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    @patch('json.load')
    def test_load_download_history_invalid_json(self, mock_json_load, mock_open, mock_exists, mock_lock):
        """Test that an error is raised when the download history file is corrupt."""
        mock_exists.return_value = True
        # Simulate an error caused by invalid JSON
        mock_json_load.side_effect = json.JSONDecodeError('Invalid JSON', '', 0)

        from synology_office_exporter.exception import DownloadHistoryError
        with self.assertRaises(DownloadHistoryError):
            with SynologyOfficeExporter(self.mock_synd, output_dir='/test/dir'):
                self.assertTrue(False)  # Should not reach here

        # Verify that the history file was attempted to be opened
        mock_exists.assert_called_once_with('/test/dir/.download_history.json')
        mock_open.assert_called_once_with('/test/dir/.download_history.json', 'r')
        mock_json_load.assert_called_once()

    @patch('synology_office_exporter.exporter.DownloadHistoryFile.lock_history')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    @patch('json.load')
    def test_load_download_history_invalid_magic(self, mock_json_load, mock_open, mock_exists, mock_lock):
        """Test that an error is raised when the download history file has an incorrect magic number."""
        mock_exists.return_value = True
        # Simulate history data with an invalid magic number
        mock_json_load.return_value = {
            '_meta': {
                'version': 1,
                'magic': 'INCORRECT_MAGIC',  # Incorrect magic number
                'created': '2023-01-01 12:00:00',
                'program': 'synology-office-exporter'
            },
            'files': {}
        }

        from synology_office_exporter.exception import DownloadHistoryError
        with self.assertRaises(DownloadHistoryError):
            with SynologyOfficeExporter(self.mock_synd, output_dir='/test/dir'):
                self.assertTrue(False)  # Should not reach here

        # Verify that the history file was attempted to be opened
        mock_exists.assert_called_once_with('/test/dir/.download_history.json')
        mock_open.assert_called_once_with('/test/dir/.download_history.json', 'r')
        mock_json_load.assert_called_once()

    @patch('synology_office_exporter.exporter.DownloadHistoryFile.lock_history')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    @patch('json.load')
    def test_load_download_history_too_new_version(self, mock_json_load, mock_open, mock_exists, mock_lock):
        """Test that an error is raised when the download history file has a version that's too new."""
        mock_exists.return_value = True
        # Simulate history data with a newer version
        mock_json_load.return_value = {
            '_meta': {
                'version': 999,  # Very new version
                'magic': HISTORY_MAGIC,
                'created': '2023-01-01 12:00:00',
                'program': 'synology-office-exporter'
            },
            'files': {}
        }

        from synology_office_exporter.exception import DownloadHistoryError
        with self.assertRaises(DownloadHistoryError):
            with SynologyOfficeExporter(self.mock_synd, output_dir='/test/dir'):
                self.assertTrue(False)  # Should not reach here

        # Verify that the history file was attempted to be opened
        mock_exists.assert_called_once_with('/test/dir/.download_history.json')
        mock_open.assert_called_once_with('/test/dir/.download_history.json', 'r')
        mock_json_load.assert_called_once()


if __name__ == '__main__':
    unittest.main()
