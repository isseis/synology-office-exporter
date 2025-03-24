"""Unit tests for the SynologyOfficeExporter download functionality."""
import json
import unittest
from unittest.mock import patch, MagicMock, call
from io import BytesIO
import os
from synology_office_exporter.exporter import HISTORY_MAGIC, SynologyOfficeExporter
from synology_office_exporter.synology_drive_api import SynologyDriveEx


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
        exporter = SynologyOfficeExporter(self.mock_synd, skip_history=True)
        exporter.save_bytesio_to_file = mock_save_bytesio_to_file
        exporter._process_document('123', 'path/to/test.osheet', hash=None)

        # Check if save_bytesio_to_file was called with correct parameters
        args, kwargs = mock_save_bytesio_to_file.call_args
        self.assertEqual(args[0].getvalue(), b'test data')
        self.assertEqual(os.path.basename(args[1]), 'test.xlsx')

        # Check if download_synology_office_file was called correctly
        self.mock_synd.download_synology_office_file.assert_called_once_with('123')

    def test_get_offline_name(self):
        # For Synology Office files, convert to MS Office extensions
        self.assertEqual(SynologyOfficeExporter.get_offline_name('test.osheet'), 'test.xlsx')
        self.assertEqual(SynologyOfficeExporter.get_offline_name('test.odoc'), 'test.docx')
        self.assertEqual(SynologyOfficeExporter.get_offline_name('test.oslides'), 'test.pptx')
        # For other files, return None
        self.assertIsNone(SynologyOfficeExporter.get_offline_name('test.txt'))

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter._process_item')
    def test_download_shared_files(self, mock_process_item):
        self.mock_synd.shared_with_me.return_value = [
            {'file_id': '123', 'content_type': 'document', 'name': 'doc1'},
            {'file_id': '456', 'content_type': 'dir', 'name': 'folder1'}
        ]

        exporter = SynologyOfficeExporter(self.mock_synd, skip_history=True)
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

        exporter = SynologyOfficeExporter(self.mock_synd, skip_history=True)
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
        exporter = SynologyOfficeExporter(self.mock_synd, skip_history=True)

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
        exporter = SynologyOfficeExporter(self.mock_synd, skip_history=True)

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
        exporter = SynologyOfficeExporter(self.mock_synd, skip_history=True)

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

        exporter = SynologyOfficeExporter(self.mock_synd, skip_history=True)
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

        exporter = SynologyOfficeExporter(self.mock_synd, skip_history=True)
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

        exporter = SynologyOfficeExporter(self.mock_synd, skip_history=True)
        exporter._process_document('123', 'path/to/test.osheet', hash=None)

        mock_download.assert_called_once_with('123')
        mock_save.assert_not_called()

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter.save_bytesio_to_file')
    def test_exception_handling_download(self, mock_save):
        """Test that exceptions during file download do not stop processing."""
        self.mock_synd.download_synology_office_file.side_effect = Exception('Download failed')

        exporter = SynologyOfficeExporter(self.mock_synd, skip_history=True)
        exporter._process_document('123', 'path/to/test.osheet', hash=None)

        # Verify download was attempted
        self.mock_synd.download_synology_office_file.assert_called_once_with('123')
        # Save should not have been called because download failed
        mock_save.assert_not_called()

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter.save_bytesio_to_file')
    def test_download_history_skips_unchanged_files(self, mock_save):
        """Test that files with unchanged hash are not re-downloaded."""
        self.mock_synd.download_synology_office_file.return_value = BytesIO(b'test data')

        exporter = SynologyOfficeExporter(self.mock_synd, skip_history=True)
        exporter.download_history = {
            'path/to/test.osheet': {
                'file_id': '123',
                'hash': 'abc123',
                'path': 'path/to/test.osheet',
                'download_time': '2023-01-01 12:00:00'
            }
        }

        # Process a document that's already in the history with the same hash
        exporter._process_document('123', 'path/to/test.osheet', 'abc123')

        # Verify that download was not attempted
        self.mock_synd.download_synology_office_file.assert_not_called()
        mock_save.assert_not_called()

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter.save_bytesio_to_file')
    def test_download_history_downloads_changed_files(self, mock_save):
        """Test that files with changed hash are re-downloaded."""
        self.mock_synd.download_synology_office_file.return_value = BytesIO(b'updated data')

        # Create exporter instance and set up download history with old hash
        exporter = SynologyOfficeExporter(self.mock_synd, skip_history=True)
        exporter.download_history = {
            'path/to/test.osheet': {
                'file_id': '123',
                'hash': 'old-hash',
                'path': 'path/to/test.osheet',
                'download_time': '2023-01-01 12:00:00'
            }
        }

        # Process a document that's in history but with a new hash
        exporter._process_document('123', 'path/to/test.osheet', 'new-hash')

        # Verify that download was attempted
        self.mock_synd.download_synology_office_file.assert_called_once_with('123')
        mock_save.assert_called_once()

        # Verify that the history was updated with the new hash
        self.assertEqual(exporter.download_history['path/to/test.osheet']['hash'], 'new-hash')

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter.save_bytesio_to_file')
    def test_download_history_saves_new_files(self, mock_save):
        """Test that new files are added to download history."""
        self.mock_synd.download_synology_office_file.return_value = BytesIO(b'new file data')

        exporter = SynologyOfficeExporter(self.mock_synd, skip_history=True)
        exporter.download_history = {}

        # Process a new document
        exporter._process_document('456', 'path/to/new.osheet', 'new-file-hash')

        # Verify that download was attempted
        self.mock_synd.download_synology_office_file.assert_called_once_with('456')
        mock_save.assert_called_once()

        # Verify that the new file was added to history
        self.assertIn('path/to/new.osheet', exporter.download_history)
        self.assertEqual(exporter.download_history['path/to/new.osheet']['file_id'], '456')
        self.assertEqual(exporter.download_history['path/to/new.osheet']['hash'], 'new-file-hash')

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter._lock_download_history')
    @patch('json.load')
    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    @patch('os.path.exists')
    def test_load_download_history(self, mock_exists, mock_open, mock_json_load, mock_lock):
        """Test that download history is correctly loaded from file."""
        mock_exists.return_value = True
        mock_json_load.return_value = {
            '_meta': {
                'version': 1,
                'magic': HISTORY_MAGIC,
                'created': '2023-01-01 12:00:00',
                'program': 'synology-office-exporter'
            },
            'files': {
                'test.osheet': {'file_id': '123', 'hash': 'abc123', 'path': 'test.osheet'},
                'test2.osheet': {'file_id': '456', 'hash': 'def456', 'path': 'test2.osheet'}
            }
        }

        with SynologyOfficeExporter(self.mock_synd, output_dir='/test/dir') as exporter:
            # _load_download_history is called in __init__, verify it worked
            mock_exists.assert_called_once_with('/test/dir/.download_history.json')
            mock_open.assert_called_once_with('/test/dir/.download_history.json', 'r')
            mock_json_load.assert_called_once()

            # Verify history was loaded correctly - files should be in download_history
            self.assertEqual(len(exporter.download_history), 2)
            self.assertEqual(exporter.download_history['test.osheet']['hash'], 'abc123')

    @patch('json.dump')
    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    @patch('os.makedirs')
    def test_save_download_history(self, mock_makedirs, mock_open, mock_json_dump):
        """Test that download history is correctly saved to file."""
        exporter = SynologyOfficeExporter(self.mock_synd, output_dir='/test/dir')
        exporter.download_history = {
            'test.osheet': {'file_id': '123', 'hash': 'abc123', 'path': 'test.osheet'},
            'test2.osheet': {'file_id': '456', 'hash': 'def456', 'path': 'test2.osheet'}
        }

        exporter._save_download_history()

        # Verify file operations
        mock_makedirs.assert_called_once_with('/test/dir', exist_ok=True)
        mock_open.assert_called_once_with('/test/dir/.download_history.json', 'w')

        # Verify the saved data (check that metadata and required file data are included)
        actual_data = mock_json_dump.call_args[0][0]
        self.assertIn('_meta', actual_data)
        self.assertIn('files', actual_data)
        self.assertEqual(actual_data['files'], exporter.download_history)
        self.assertEqual(actual_data['_meta']['magic'], HISTORY_MAGIC)
        self.assertEqual(actual_data['_meta']['version'], 1)
        self.assertEqual(actual_data['_meta']['program'], 'synology-office-exporter')

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter._unlock_download_history')
    @patch('synology_office_exporter.exporter.SynologyOfficeExporter._lock_download_history')
    @patch('synology_office_exporter.exporter.SynologyOfficeExporter._process_directory')
    @patch('synology_office_exporter.exporter.SynologyOfficeExporter._save_download_history')
    @patch('synology_office_exporter.exporter.SynologyOfficeExporter._load_download_history')
    def test_context_manager(self, mock_load, mock_save, mock_process, mock_lock, mock_unlock):
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

        exporter = SynologyOfficeExporter(self.mock_synd, output_dir='.', force_download=True, skip_history=True)
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

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter._lock_download_history')
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

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter._lock_download_history')
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

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter._lock_download_history')
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
