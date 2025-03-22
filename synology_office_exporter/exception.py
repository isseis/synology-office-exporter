"""
This file defines error classes specific to SynologyOfficeExporter.

These custom exceptions are used throughout the application to handle
specific error conditions that can occur during operations with Synology Office.
"""


class DownloadHistoryError(Exception):
    """
    Exception raised for errors related to download history operations.

    This exception is used when there are issues with retrieving,
    parsing, or processing download history from the Synology Office server.
    """

    pass
