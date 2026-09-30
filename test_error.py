import unittest
from unittest.mock import patch, Mock

from sales_data import SalesDataProcessorApp, SalesFileProcessor


class TestAPIAndErrorLog(unittest.TestCase):

    def setUp(self):
        # Create application object without opening the Tkinter window
        self.app = object.__new__(SalesDataProcessorApp)
        self.app.log_message = Mock()

        # Create error log processor
        self.processor = SalesFileProcessor()

    # =========================
    # API TESTING
    # =========================

    # Test successful API connection
    @patch("sales_data.urllib.request.urlopen")
    def test_api_connection_success(self, mock_urlopen):

        mock_response = Mock()
        mock_response.read.return_value = (
            b'["12345678-1234-1234-1234-123456789abc"]'
        )

        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = self.app._get_api_uuid()

        self.assertEqual(
            result,
            "12345678-1234-1234-1234-123456789abc"
        )

    # Test API failure and local UUID fallback
    @patch("sales_data.urllib.request.urlopen")
    @patch("sales_data.uuid.uuid1")
    def test_api_connection_failure(
        self,
        mock_uuid1,
        mock_urlopen
    ):

        mock_urlopen.side_effect = Exception(
            "API connection failed"
        )

        mock_uuid1.return_value = "local-test-uuid"

        result = self.app._get_api_uuid()

        # Check that local UUID was returned
        self.assertEqual(result, "local-test-uuid")

        # Check that the failure was logged
        self.app.log_message.assert_called_once()

    # =========================
    # ERROR LOG TESTING
    # =========================

    # Test adding an error log
    def test_add_error_log(self):

        self.processor.add_error_log(
            "error.csv",
            "Invalid CSV data"
        )

        # Check that one error was added
        self.assertEqual(
            len(self.processor.error_logs),
            1
        )

        filename, message, timestamp = (
            self.processor.error_logs[0]
        )

        self.assertEqual(
            filename,
            "error.csv"
        )

        self.assertEqual(
            message,
            "Invalid CSV data"
        )

        # Check that timestamp exists
        self.assertTrue(timestamp)

    def test_add_error_log_notifies_observers(self):
        observer = Mock()
        self.processor.add_error_log_observer(observer)

        self.processor.add_error_log("error.csv", "Invalid CSV data")

        observer.assert_called_once_with(
            "error.csv",
            "Invalid CSV data",
            self.processor.error_logs[0][2],
        )

    def test_removed_error_log_observer_is_not_notified(self):
        observer = Mock()
        self.processor.add_error_log_observer(observer)
        self.processor.remove_error_log_observer(observer)

        self.processor.add_error_log("error.csv", "Invalid CSV data")

        observer.assert_not_called()

    # Test multiple error logs
    def test_multiple_error_logs(self):

        self.processor.add_error_log(
            "error1.csv",
            "Invalid header"
        )

        self.processor.add_error_log(
            "error2.csv",
            "Duplicate transaction ID"
        )

        # Check that two errors were stored
        self.assertEqual(
            len(self.processor.error_logs),
            2
        )

        self.assertEqual(
            self.processor.error_logs[0][0],
            "error1.csv"
        )

        self.assertEqual(
            self.processor.error_logs[1][0],
            "error2.csv"
        )


if __name__ == "__main__":
    unittest.main()