"""Unit tests for the SynologyOfficeExporter download functionality."""
import unittest
from unittest.mock import patch, MagicMock, call
from io import BytesIO
from synology_office_exporter.exporter import SynologyOfficeExporter
from synology_office_exporter.synology_drive_api import SynologyDriveEx
from tests.mock_download_history import MockDownloadHistory


class TestDownload(unittest.TestCase):
    """Test suite for the SynologyOfficeExporter download functionality."""

    def setUp(self):
        self.mock_synd = MagicMock(spec=SynologyDriveEx)

    def test_process_document(self):
        """Test processing a document file."""
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

        with patch.object(SynologyOfficeExporter, 'save_bytesio_to_file') as mock_save:
            exporter = SynologyOfficeExporter(self.mock_synd, MockDownloadHistory(), output_dir='/test/dir')
            exporter._process_document('123', 'path/to/test.osheet', hash=None)

        # Check if download_synology_office_file was called correctly
        self.mock_synd.download_synology_office_file.assert_called_once_with('123')

        # Check if save_bytesio_to_file was called with correct parameters
        args, kwargs = mock_save.call_args
        self.assertEqual(args[0].getvalue(), b'test data')
        self.assertEqual(args[1], '/test/dir/path/to/test.xlsx')

    def test_convert_synology_to_ms_office_filename(self):
        """Test conversion of Synology Office filenames to MS Office filenames."""
        # For Synology Office files, convert to MS Office extensions
        self.assertEqual(SynologyOfficeExporter.convert_synology_to_ms_office_filename('test.osheet'), 'test.xlsx')
        self.assertEqual(SynologyOfficeExporter.convert_synology_to_ms_office_filename('test.odoc'), 'test.docx')
        self.assertEqual(SynologyOfficeExporter.convert_synology_to_ms_office_filename('test.oslides'), 'test.pptx')
        # For other files, return None
        self.assertIsNone(SynologyOfficeExporter.convert_synology_to_ms_office_filename('test.txt'))

    def test_download_shared_files(self):
        """Test downloading files shared with the user."""
        self.mock_synd.shared_with_me.return_value = [
            {'file_id': '123', 'content_type': 'document', 'name': 'doc1'},
            {'file_id': '456', 'content_type': 'dir', 'name': 'folder1'}
        ]

        with patch.object(SynologyOfficeExporter, '_process_item') as mock_process_item:
            exporter = SynologyOfficeExporter(self.mock_synd, MockDownloadHistory())
            exporter._download_shared_files()

        # Verify _process_item was called for each shared item
        self.assertEqual(mock_process_item.call_count, 2)
        mock_process_item.assert_has_calls([
            call({'file_id': '123', 'content_type': 'document', 'name': 'doc1'}),
            call({'file_id': '456', 'content_type': 'dir', 'name': 'folder1'})
        ])

    def test_download_teamfolder_files(self):
        """Test downloading files from team folders."""
        self.mock_synd.get_teamfolder_info.return_value = {
            'Team Folder 1': '789',
            'Team Folder 2': '012'
        }

        with patch.object(SynologyOfficeExporter, '_process_directory') as mock_process_directory:
            exporter = SynologyOfficeExporter(self.mock_synd, MockDownloadHistory())
            exporter._download_teamfolder_files()

        # Verify _process_directory was called for each team folder
        self.assertEqual(mock_process_directory.call_count, 2)
        mock_process_directory.assert_has_calls([
            call('789', 'Team Folder 1'),
            call('012', 'Team Folder 2')
        ], any_order=True)  # Order of dictionary items is not guaranteed

    def test_process_item_dir(self):
        """Test processing a directory item."""
        item = {
            'file_id': '456',
            'content_type': 'dir',
            'display_path': 'path/to/folder'
        }
        with patch.object(SynologyOfficeExporter, '_process_directory') as mock_process_directory, \
                patch.object(SynologyOfficeExporter, '_process_document') as mock_process_document:
            exporter = SynologyOfficeExporter(self.mock_synd, MockDownloadHistory())
            exporter._process_item(item)

        mock_process_directory.assert_called_once_with('456', 'path/to/folder')
        mock_process_document.assert_not_called()

    def test_process_item_doc(self):
        """Test processing a non-encrypted document item."""
        item = {
            'file_id': '123',
            'content_type': 'document',
            'display_path': 'path/to/doc.osheet',
            'encrypted': False
        }

        with patch.object(SynologyOfficeExporter, '_process_directory') as mock_process_directory, \
                patch.object(SynologyOfficeExporter, '_process_document') as mock_process_document:
            exporter = SynologyOfficeExporter(self.mock_synd, MockDownloadHistory())
            exporter._process_item(item)

        # Modify this line to check with positional arguments instead of keyword arguments
        mock_process_document.assert_called_once_with('123', 'path/to/doc.osheet', None)
        mock_process_directory.assert_not_called()

    def test_process_item_encrypted_doc(self):
        """Test processing an encrypted document item."""
        item = {
            'file_id': '789',
            'content_type': 'document',
            'display_path': 'path/to/secret.osheet',
            'encrypted': True
        }

        with patch.object(SynologyOfficeExporter, '_process_directory') as mock_process_directory, \
                patch.object(SynologyOfficeExporter, '_process_document') as mock_process_document:
            exporter = SynologyOfficeExporter(self.mock_synd, MockDownloadHistory())
            exporter._process_item(item)

        mock_process_document.assert_not_called()
        mock_process_directory.assert_not_called()

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter._process_directory')
    def test_download_mydrive_files(self, mock_process_directory):
        exporter = SynologyOfficeExporter(self.mock_synd, MockDownloadHistory())

        exporter._download_mydrive_files()
        mock_process_directory.assert_called_once_with('/mydrive', 'My Drive')

    def test_exception_handling_shared_files(self):
        """Test that the program continues downloading even if some files cause exceptions."""
        # Set up mock to have 3 files, with processing of the second one raising an exception
        self.mock_synd.shared_with_me.return_value = [
            {'file_id': '123', 'content_type': 'document', 'name': 'doc1'},
            {'file_id': '456', 'content_type': 'dir', 'name': 'folder1'},
            {'file_id': '789', 'content_type': 'document', 'name': 'doc2'}
        ]

        with patch.object(SynologyOfficeExporter, '_process_item') as mock_process_item:
            # Make the second file raise an exception when processed
            def side_effect(item):
                if item['file_id'] == '456':
                    raise Exception('Test error')
                return None
            mock_process_item.side_effect = side_effect
            exporter = SynologyOfficeExporter(self.mock_synd, MockDownloadHistory())
            exporter._download_shared_files()

        # Verify all items were attempted to be processed, despite the exception
        self.assertEqual(mock_process_item.call_count, 3)
        mock_process_item.assert_any_call({'file_id': '123', 'content_type': 'document', 'name': 'doc1'})
        mock_process_item.assert_any_call({'file_id': '456', 'content_type': 'dir', 'name': 'folder1'})
        mock_process_item.assert_any_call({'file_id': '789', 'content_type': 'document', 'name': 'doc2'})

    def test_exception_handling_mydrive(self):
        """Test that exceptions in _process_directory do not stop execution."""
        with patch.object(SynologyOfficeExporter, '_process_directory') as mock_process_directory:
            mock_process_directory.side_effect = Exception('Test error')
            exporter = SynologyOfficeExporter(self.mock_synd, MockDownloadHistory())
            exporter._download_mydrive_files()

        # Verify _process_directory was called with correct parameters
        mock_process_directory.assert_called_once_with('/mydrive', 'My Drive')

    def test_exception_handling_teamfolders(self):
        """Test that exceptions in one team folder do not prevent processing other folders."""
        self.mock_synd.get_teamfolder_info.return_value = {
            'Team Folder 1': '111',
            'Team Folder 2': '222',
            'Team Folder 3': '333'
        }

        with patch.object(SynologyOfficeExporter, '_process_directory') as mock_process_directory:
            # Make processing of 'Team Folder 2' raise an exception
            def side_effect(file_id, name):
                if file_id == '222':
                    raise Exception('Test error')
                return None
            mock_process_directory.side_effect = side_effect
            exporter = SynologyOfficeExporter(self.mock_synd, MockDownloadHistory())
            exporter._download_teamfolder_files()

        # Verify all team folders were attempted to be processed
        self.assertEqual(mock_process_directory.call_count, 3)
        mock_process_directory.assert_any_call('111', 'Team Folder 1')
        mock_process_directory.assert_any_call('222', 'Team Folder 2')
        mock_process_directory.assert_any_call('333', 'Team Folder 3')

    def test_exception_handling_download_synology(self):
        """Test that exceptions during file download do not stop processing."""
        with patch.object(SynologyOfficeExporter, 'save_bytesio_to_file') as mock_save:
            self.mock_synd.download_synology_office_file.side_effect = Exception('Download failed')

            exporter = SynologyOfficeExporter(self.mock_synd, MockDownloadHistory())
            exporter._process_document('123', 'path/to/test.osheet', hash=None)
        # Verify no exceptions were raised and the download was attempted.

        self.mock_synd.download_synology_office_file.assert_called_once_with('123')
        mock_save.assert_not_called()

    def test_download_history_skips_should_not_download_files(self):
        """Test that files already in download history are skipped."""
        download_history = MagicMock()
        download_history.should_download.return_value = False
        with SynologyOfficeExporter(self.mock_synd, download_history) as exporter:
            exporter._process_document('123', 'path/to/test.osheet', 'old-hash')

        # Verify that download was not attempted
        self.mock_synd.download_synology_office_file.assert_not_called()

    def test_download_history_saves_files(self):
        """Test that new files are added to download history."""
        self.mock_synd.download_synology_office_file.return_value = BytesIO(b'new file data')
        download_history = MagicMock()
        with patch.object(SynologyOfficeExporter, 'save_bytesio_to_file') as mock_save, \
                SynologyOfficeExporter(self.mock_synd, download_history) as exporter:
            exporter._process_document('456', 'path/to/new.osheet', 'new-file-hash')

        # Verify that download was attempted
        self.mock_synd.download_synology_office_file.assert_called_once_with('456')
        mock_save.assert_called_once()
        download_history.add_history_entry.assert_called_once_with(
            'path/to/new.osheet', '456', 'new-file-hash')

    def test_load_download_history(self):
        """Test that custom download history storage is properly used."""
        # Create the mock download history instance
        download_history = MockDownloadHistory()

        # Use the custom history storage with the exporter
        with patch.object(SynologyOfficeExporter, 'save_bytesio_to_file'), \
                SynologyOfficeExporter(self.mock_synd, download_history, output_dir='/test/dir',) as exporter:
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

    def test_context_manager(self):
        """Test that context manager loads and saves download history."""
        mock_download_history = MockDownloadHistory()
        with patch.object(SynologyOfficeExporter, '_process_directory') as mock_process, \
                SynologyOfficeExporter(self.mock_synd, mock_download_history, output_dir='/test/dir') as exporter:
            # In the context, lock and load should have been called already
            self.assertTrue(mock_download_history.lock_called)
            self.assertTrue(mock_download_history.load_called)
            # save and unlock shouldn't be called yet.
            self.assertFalse(mock_download_history.save_called)
            self.assertFalse(mock_download_history.unlock_called)

            # Do something with the exporter
            exporter._download_mydrive_files()

        # After the context, _save_download_history should have been called
        mock_process.assert_called_once()
        self.assertTrue(mock_download_history.save_called)
        self.assertTrue(mock_download_history.unlock_called)


if __name__ == '__main__':
    unittest.main()
