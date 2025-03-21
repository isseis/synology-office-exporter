"""
Tests for the functionality that removes output files when Synology Office files are deleted.
"""

import os
import unittest
from unittest.mock import patch, MagicMock, mock_open
from io import BytesIO

from synology_office_exporter.exporter import SynologyOfficeExporter


class TestDeletedFiles(unittest.TestCase):
    """Test suite for verifying proper cleanup of exported files when original Synology Office files are deleted."""

    def setUp(self):
        """Set up test environment before each test."""
        self.mock_synd = MagicMock()

        self.output_dir = "/tmp/synology_office_exports"
        self.history_file = os.path.join(self.output_dir, ".download_history.json")

        self.sample_history = {
            "file_id_1": {
                "hash": "hash1",
                "path": "/path/to/document.odoc",
                "output_path": os.path.join(self.output_dir, "document.docx"),
                "download_time": "2023-01-01 12:00:00"
            },
            "file_id_2": {
                "hash": "hash2",
                "path": "/path/to/spreadsheet.osheet",
                "output_path": os.path.join(self.output_dir, "spreadsheet.xlsx"),
                "download_time": "2023-01-01 12:00:00"
            }
        }

    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    @patch("json.load")
    def test_load_download_history(self, mock_json_load, mock_file_open, mock_path_exists):
        """Test that download history is loaded correctly."""
        mock_path_exists.return_value = True
        mock_json_load.return_value = self.sample_history

        exporter = SynologyOfficeExporter(self.mock_synd, output_dir=self.output_dir)

        # Verify file was opened and history was loaded
        mock_file_open.assert_called_once_with(self.history_file, 'r')
        self.assertEqual(exporter.download_history, self.sample_history)

    @patch("os.path.exists")
    @patch("os.remove")
    def test_remove_deleted_files(self, mock_remove, mock_path_exists):
        """Test that files deleted from NAS are removed from the output directory."""
        # Mock file existence check to always return True
        mock_path_exists.return_value = True

        with patch.object(SynologyOfficeExporter, '_load_download_history'):
            exporter = SynologyOfficeExporter(self.mock_synd, output_dir=self.output_dir)
            exporter.download_history = self.sample_history.copy()

            # Simulate that one file still exists on NAS (file_id_1) and one is deleted (file_id_2)
            exporter.current_file_ids = {"file_id_1"}

            # Call the method to test
            exporter._remove_deleted_files()

            # Check that os.remove was called for the deleted file
            mock_remove.assert_called_once_with(self.sample_history["file_id_2"]["output_path"])

            # Check that the deleted file is removed from history
            self.assertNotIn("file_id_2", exporter.download_history)
            self.assertIn("file_id_1", exporter.download_history)

            # Check that the counter was incremented
            self.assertEqual(exporter.deleted_files, 1)

    @patch("os.path.exists")
    @patch("os.remove")
    def test_no_files_to_remove(self, mock_remove, mock_path_exists):
        """Test that no files are removed when all files still exist on NAS."""
        mock_path_exists.return_value = True

        with patch.object(SynologyOfficeExporter, '_load_download_history'):
            exporter = SynologyOfficeExporter(self.mock_synd, output_dir=self.output_dir)
            exporter.download_history = self.sample_history.copy()

            # Simulate that all files still exist on the NAS
            exporter.current_file_ids = {"file_id_1", "file_id_2"}

            # Call the method to test
            exporter._remove_deleted_files()

            # Check that os.remove was not called
            mock_remove.assert_not_called()

            # Check that the history is unchanged
            self.assertEqual(len(exporter.download_history), 2)

            # Check that the counter wasn't incremented
            self.assertEqual(exporter.deleted_files, 0)

    @patch("os.path.exists")
    @patch("os.remove")
    def test_file_already_removed(self, mock_remove, mock_path_exists):
        """Test handling of files that are already removed from the filesystem."""
        # Mock file existence check to return False (file is already gone)
        mock_path_exists.return_value = False

        with patch.object(SynologyOfficeExporter, '_load_download_history'):
            exporter = SynologyOfficeExporter(self.mock_synd, output_dir=self.output_dir)
            exporter.download_history = self.sample_history.copy()

            # Simulate that one file is deleted from NAS
            exporter.current_file_ids = {"file_id_1"}

            # Call the method to test
            exporter._remove_deleted_files()

            # Check that os.remove was not called (because file doesn't exist)
            mock_remove.assert_not_called()

            # Check that the file is still removed from history
            self.assertNotIn("file_id_2", exporter.download_history)

            # Check that the counter wasn't incremented (no actual deletion)
            self.assertEqual(exporter.deleted_files, 0)

    @patch("os.makedirs")
    @patch("builtins.open", new_callable=mock_open)
    @patch("json.dump")
    def test_save_updated_history(self, mock_json_dump, mock_file_open, mock_makedirs):
        """Test that updated history (after removal) is saved correctly."""
        with patch.object(SynologyOfficeExporter, '_load_download_history'):
            exporter = SynologyOfficeExporter(self.mock_synd, output_dir=self.output_dir)

            # Set a partial history (as if file_id_2 was deleted)
            exporter.download_history = {"file_id_1": self.sample_history["file_id_1"]}

            # Call exit to trigger save
            exporter.__exit__(None, None, None)

            # Verify history was saved with updated content
            mock_file_open.assert_called_with(self.history_file, 'w')
            mock_json_dump.assert_called_once()
            # Verify that file_id_2 is not in the saved history
            saved_history = mock_json_dump.call_args[0][0]
            self.assertNotIn("file_id_2", saved_history)

    @patch("os.path.exists")
    def test_end_to_end_process(self, mock_path_exists):
        """Test the complete process of tracking and removing deleted files."""
        mock_path_exists.return_value = True

        # Mock SynologyDriveEx methods
        mock_list_resp = {
            "success": True,
            "data": {"items": [
                {"file_id": "file_id_1", "name": "document.odoc", "content_type": "document", "hash": "hash1"},
                # file_id_2 is missing, simulating it was deleted from NAS
            ]}
        }
        self.mock_synd.list_folder.return_value = mock_list_resp
        self.mock_synd.download_synology_office_file.return_value = BytesIO(b"file content")

        with patch.object(SynologyOfficeExporter, '_load_download_history'), \
                patch.object(SynologyOfficeExporter, '_save_download_history'), \
                patch.object(SynologyOfficeExporter, 'save_bytesio_to_file'), \
                patch('os.remove') as mock_remove:

            exporter = SynologyOfficeExporter(self.mock_synd, output_dir=self.output_dir)
            exporter.download_history = self.sample_history.copy()

            # Process directory which only has file_id_1 now
            exporter._process_directory("dir_id", "test_dir")

            # Exit to trigger the removal of deleted files
            exporter.__exit__(None, None, None)

            # Verify file_id_2 was removed
            mock_remove.assert_called_once_with(self.sample_history["file_id_2"]["output_path"])

            # Check history was updated
            self.assertNotIn("file_id_2", exporter.download_history)

            # Check counters
            self.assertEqual(exporter.deleted_files, 1)


if __name__ == "__main__":
    unittest.main()
