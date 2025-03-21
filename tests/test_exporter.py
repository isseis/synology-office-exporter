"""
Tests for the main SynologyOfficeExporter class.
"""

import unittest
from unittest.mock import patch, MagicMock, mock_open
from io import BytesIO
import os

from synology_office_exporter.exporter import SynologyOfficeExporter


class TestSynologyOfficeExporter(unittest.TestCase):
    """Test suite for the SynologyOfficeExporter class."""

    def setUp(self):
        """Set up test environment before each test."""
        # Create a mock SynologyDriveEx instance
        self.mock_synd = MagicMock()
        self.output_dir = "/tmp/synology_office_exports"

    def test_get_offline_name(self):
        """Test conversion of Synology Office filenames to MS Office filenames."""
        self.assertEqual(
            SynologyOfficeExporter.get_offline_name("document.odoc"),
            "document.docx"
        )
        self.assertEqual(
            SynologyOfficeExporter.get_offline_name("spreadsheet.osheet"),
            "spreadsheet.xlsx"
        )
        self.assertEqual(
            SynologyOfficeExporter.get_offline_name("presentation.oslides"),
            "presentation.pptx"
        )
        self.assertIsNone(
            SynologyOfficeExporter.get_offline_name("not_office_file.txt")
        )

    @patch("os.makedirs")
    @patch("builtins.open", new_callable=mock_open)
    def test_save_bytesio_to_file(self, mock_file_open, mock_makedirs):
        """Test saving BytesIO content to a file."""
        test_content = b"test content"
        test_path = os.path.join(self.output_dir, "test.docx")

        # Create BytesIO with test content
        data = BytesIO(test_content)

        SynologyOfficeExporter.save_bytesio_to_file(data, test_path)

        # Verify directory was created
        mock_makedirs.assert_called_once_with(self.output_dir, exist_ok=True)

        # Verify file was opened correctly
        mock_file_open.assert_called_once_with(test_path, 'wb')

        # Verify content was written
        mock_file_open().write.assert_called_once_with(test_content)

    @patch("builtins.open", new_callable=mock_open)
    @patch("json.dump")
    def test_save_download_history(self, mock_json_dump, mock_file_open):
        """Test that download history is saved correctly."""
        with patch.object(SynologyOfficeExporter, '_load_download_history'):
            exporter = SynologyOfficeExporter(self.mock_synd, output_dir=self.output_dir)

            # Set a sample history
            sample_history = {
                "file_id_1": {
                    "hash": "hash1",
                    "path": "/path/to/document.odoc",
                    "output_path": os.path.join(self.output_dir, "document.docx"),
                    "download_time": "2023-01-01 12:00:00"
                }
            }
            exporter.download_history = sample_history

            # Trigger save
            exporter._save_download_history()

            # Verify file was opened correctly
            history_file = os.path.join(self.output_dir, ".download_history.json")
            mock_file_open.assert_called_with(history_file, 'w')

            # Verify history was dumped
            mock_json_dump.assert_called_once_with(sample_history, mock_file_open())

    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    @patch("json.load")
    def test_process_document_tracking(self, mock_json_load, mock_file_open, mock_path_exists):
        """Test that documents are properly tracked for deletion detection."""
        mock_path_exists.return_value = True
        mock_json_load.return_value = {}

        # Mock BytesIO for download
        mock_data = BytesIO(b"test content")
        self.mock_synd.download_synology_office_file.return_value = mock_data

        with patch.object(SynologyOfficeExporter, 'save_bytesio_to_file'):
            exporter = SynologyOfficeExporter(self.mock_synd, output_dir=self.output_dir)

            # Clear any auto-loaded history
            exporter.current_file_ids = set()

            # Process a document - should add to current_file_ids
            exporter._process_document("test_file_id", "/path/to/document.odoc", "hash123")

            # Verify the file ID was added to the tracking set
            self.assertIn("test_file_id", exporter.current_file_ids)


if __name__ == "__main__":
    unittest.main()
