"""
Test suite for the DownloadHistoryFile class.
"""
import os
import unittest

from datetime import datetime
from synology_office_exporter.download_history import HISTORY_MAGIC, DownloadHistoryFile
from unittest.mock import patch


class TestDownloadHistory(unittest.TestCase):
    """Test suite for the DownloadHistoryFile class."""

    def setUp(self):
        """Set up test environment before each test."""
        # Create a mock SynologyDriveEx instance
        self.output_dir = '/tmp/synology_office_exports'

    @patch('json.load')
    @patch('builtins.open')
    @patch('os.path.exists')
    def test_load_download_history(self, mock_exists, mock_open, mock_json_load):
        """Test loading download history from a file."""
        mock_json_load.return_value = {
            '_meta': {
                'version': 1,
                'magic': HISTORY_MAGIC,
                'created': '2025-03-22 14:43:44.966404',
                'program': 'synology-office-exporter'
            },
            'files': {
                '/path/to/document.odoc': {
                    'hash': 'hash1',
                    'file_id': 'file_id_1',
                    'download_time': '2023-01-01 12:00:00'
                }
            }
        }

        mock_exists.return_value = True
        history_storage = DownloadHistoryFile(output_dir=self.output_dir, skip_lock=True)
        history_storage.load_history()

        # Verify loaded history
        mock_open.assert_called_once_with(os.path.join(self.output_dir, '.download_history.json'), 'r')
        self.assertEqual(history_storage.get_history_entry('/path/to/document.odoc'), {
            'hash': 'hash1',
            'file_id': 'file_id_1',
            'download_time': '2023-01-01 12:00:00',
        })

    def test_should_download_force_download(self):
        """Test should_download when force_download is True."""
        # Create history with force_download=True
        history = DownloadHistoryFile(self.output_dir, force_download=True)

        # Manually add a file to history without saving
        history.add_history_entry('test_file.doc', 'file_id_123', 'hash123')

        # Even with file in history, should return True because force_download is True
        self.assertTrue(history.should_download('test_file.doc', 'hash123'))

    def test_should_download_file_not_in_history(self):
        """Test should_download when file is not in download history."""
        # Create history object
        history = DownloadHistoryFile(self.output_dir, skip_lock=True)

        # File not in history should return True
        self.assertTrue(history.should_download('nonexistent_file.doc', 'hash456'))

    def test_should_download_hash_comparison(self):
        """Test should_download hash comparison logic."""
        # Create history object
        history = DownloadHistoryFile(self.output_dir, skip_lock=True)

        # Add a file to history
        file_path = 'test_file.doc'
        original_hash = 'original_hash'

        # New file, should download
        self.assertTrue(history.should_download(file_path, original_hash))

        history.add_history_entry(file_path, 'file_id_123', original_hash)

        # Same hash, should not download
        self.assertFalse(history.should_download(file_path, original_hash))

        # Different hash, should download
        new_hash = 'new_hash'
        self.assertTrue(history.should_download(file_path, new_hash))

    @patch('json.dump')
    @patch('builtins.open')
    @patch('os.makedirs')
    def test_save_download_history(self, mock_makedirs, mock_open, mock_json_dump):
        """Test that download history is correctly saved to file."""
        history = DownloadHistoryFile(self.output_dir, skip_lock=True)
        history.add_history_entry('test.osheet', '123', 'abc123', datetime(2023, 1, 1, 12, 0, 0))
        history.add_history_entry('test2.osheet', '456', 'def456', datetime(2023, 1, 2, 12, 0, 0))
        history.save_history()

        # Verify file operations
        mock_open.assert_called_once_with(os.path.join(self.output_dir, '.download_history.json'), 'w')
        mock_makedirs.assert_called_once_with(self.output_dir, exist_ok=True)

        # Verify the saved data (check that metadata and required file data are included)
        actual_data = mock_json_dump.call_args[0][0]
        self.assertIn('_meta', actual_data)
        self.assertIn('files', actual_data)
        self.assertEqual(history.get_history_keys(), set(['test.osheet', 'test2.osheet']))
        self.assertEqual({
            'file_id': '123',
            'hash': 'abc123',
            'download_time': '2023-01-01 12:00:00',
        }, history.get_history_entry('test.osheet'))
        self.assertEqual({
            'file_id': '456',
            'hash': 'def456',
            'download_time': '2023-01-02 12:00:00',
        }, history.get_history_entry('test2.osheet'))
        self.assertEqual(actual_data['_meta']['magic'], HISTORY_MAGIC)
        self.assertEqual(actual_data['_meta']['version'], 1)
        self.assertEqual(actual_data['_meta']['program'], 'synology-office-exporter')
