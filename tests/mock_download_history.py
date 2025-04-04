"""Mock implementation of DownloadHistory for testing."""
from synology_office_exporter.download_history import DownloadHistory


class MockDownloadHistory(DownloadHistory):
    """Mock implementation of DownloadHistory for testing."""

    def __init__(self):
        super().__init__()
        self.lock_called = False
        self.unlock_called = False
        self.load_called = False
        self.save_called = False
        self.should_download_called = False
        self.add_history_called = False
        self.get_keys_called = False
        self.remove_entry_called = False

    def lock_history(self):
        """Mock implementation of lock_history method."""
        self.lock_called = True

    def unlock_history(self):
        """Mock implementation of unlock_history method."""
        self.unlock_called = True

    def load_history(self):
        """Mock implementation of load_history method."""
        self.load_called = True

    def save_history(self):
        """Mock implementation of save_history method."""
        self.save_called = True

    def should_download(self, file_path, hash_value):
        """Mock implementation of should_download method."""
        self.should_download_called = True
        return True

    def add_history_entry(self, path, file_id, hash, download_time=None):
        """Mock implementation of add_history_entry method."""
        self.add_history_called = True

    def get_history_keys(self):
        """Mock implementation of get_history_keys method."""
        self.get_keys_called = True
        return set([])

    def remove_history_entry(self, file_path):
        """Mock implementation of remove_history_entry method."""
        self.remove_entry_called = True
