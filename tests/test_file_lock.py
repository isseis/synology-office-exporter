"""
Tests for file locking functionality in SynologyOfficeExporter class.
"""

import tempfile
import unittest
from unittest.mock import patch, MagicMock

from filelock import Timeout
from io import StringIO

from synology_office_exporter.download_history import DownloadHistoryFile
from synology_office_exporter.exception import DownloadHistoryError
from synology_office_exporter.exporter import SynologyOfficeExporter


class TestFileLock(unittest.TestCase):
    """Test file locking behavior in SynologyOfficeExporter."""

    def setUp(self):
        """Set up test environment with temporary directory and mock objects."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.synd_mock = MagicMock()
        self.stat_buf = StringIO()

    def tearDown(self):
        """Clean up temporary directory."""
        self.temp_dir.cleanup()

    def test_enter_exit_acquires_and_releases_lock(self):
        """Test that __enter__ acquires a lock and __exit__ releases it."""
        with patch('synology_office_exporter.download_history.FileLock') as mock_filelock:
            mock_lock = MagicMock()
            mock_filelock.return_value = mock_lock

            history_file = DownloadHistoryFile()
            history_file.lock_history()
            history_file.unlock_history()

            mock_filelock.assert_called_once()
            mock_lock.acquire.assert_called_once_with(blocking=False)
            mock_lock.release.assert_called_once()

    def test_timeout_exception_when_lock_exists(self):
        """Test that a DownloadHistoryError is raised when the lock cannot be acquired."""
        with patch('synology_office_exporter.download_history.FileLock') as mock_filelock:
            mock_lock = MagicMock()
            mock_filelock.return_value = mock_lock
            mock_lock.acquire.side_effect = Timeout('lock_file')

            history_file = DownloadHistoryFile()
            with self.assertRaises(DownloadHistoryError):
                history_file.lock_history()

    def test_lock_release_on_exception(self):
        """Test that lock is released even when an exception occurs within the context."""
        with patch('synology_office_exporter.download_history.FileLock') as mock_filelock, \
                patch('synology_office_exporter.download_history.DownloadHistoryFile.load_history'), \
                patch('synology_office_exporter.download_history.DownloadHistoryFile.save_history'):
            mock_lock = MagicMock()
            mock_filelock.return_value = mock_lock

            try:
                with DownloadHistoryFile():
                    raise RuntimeError('Test exception')
            except RuntimeError:
                pass

            mock_lock.release.assert_called_once()


class TestFileLockIntegration(unittest.TestCase):
    """Integration tests for file locking behavior with actual filesystem."""

    def setUp(self):
        """Set up test environment with temporary directory and mock objects."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.synd_mock = MagicMock()

    def tearDown(self):
        """Clean up temporary directory."""
        self.temp_dir.cleanup()

    @patch('synology_office_exporter.download_history.DownloadHistoryFile.load_history')
    def test_concurrent_access_prevention(self, mock_load):
        """Test that a second instance cannot acquire the lock when first one holds it."""
        # First instance
        with SynologyOfficeExporter(self.synd_mock, output_dir=self.temp_dir.name):
            # Try to create a second instance that should fail
            with self.assertRaises(DownloadHistoryError):
                with SynologyOfficeExporter(self.synd_mock, output_dir=self.temp_dir.name):
                    self.assertTrue(False)  # Should not reach here

        # Verify lock file is released by creating a new instance after cleanup
        with SynologyOfficeExporter(self.synd_mock, output_dir=self.temp_dir.name):
            # If we get here, it means the lock was successfully acquired
            self.assertTrue(True)


if __name__ == '__main__':
    unittest.main()
