import unittest
from unittest.mock import Mock, patch

from sales_data import SalesDataProcessorApp, SalesFileProcessor


class TestValidation(unittest.TestCase):

    def setUp(self):
        # Create the app object without opening the Tkinter window
        self.app = object.__new__(SalesDataProcessorApp)
        self.app.log_message = Mock()

    def test_valid_csv(self):
        csv_data = """transaction_id,timestamp,store_id,product_id,quantity,unit_price,total_amount,payment_method
TX001,2026-08-18 09:00:00,S001,P001,2,10,20,Cash"""

        result, message = self.app._evaluate_content_rules(
            "SALES_DATA_20260818090000.csv",
            csv_data,
            True
        )

        self.assertTrue(result)
        self.assertEqual(message, "Passed")

    def test_invalid_headers(self):
        csv_data = """id,timestamp,store_id,product_id,quantity,unit_price,total_amount,payment_method
TX001,2026-08-18 09:00:00,S001,P001,2,10,20,Cash"""

        result, message = self.app._evaluate_content_rules(
            "SALES_DATA_20260818090000.csv",
            csv_data,
            True
        )

        self.assertFalse(result)
        self.assertIn("Missing or incorrectly named headers", message)

    def test_unsupported_filename_is_added_to_error_logs(self):
        filename = "sales_data.txt"
        self.app.selected_file = filename
        self.app.processor = SalesFileProcessor()

        with patch("sales_data.messagebox.showerror"):
            result, message = self.app.validate_selected_file()

        self.assertFalse(result)
        self.assertIn("unsupported file extension", message)
        self.assertEqual(len(self.app.processor.error_logs), 1)
        logged_filename, logged_message, _ = self.app.processor.error_logs[0]
        self.assertEqual(logged_filename, filename)
        self.assertEqual(logged_message, message)

    def test_empty_field(self):
        csv_data = """transaction_id,timestamp,store_id,product_id,quantity,unit_price,total_amount,payment_method
TX001,2026-08-18 09:00:00,S001,P001,,10,20,Cash"""

        result, message = self.app._evaluate_content_rules(
            "SALES_DATA_20260818090000.csv",
            csv_data,
            True
        )

        self.assertFalse(result)
        self.assertIn("Empty cell value discovered", message)

    def test_duplicate_transaction_id(self):
        csv_data = """transaction_id,timestamp,store_id,product_id,quantity,unit_price,total_amount,payment_method
TX001,2026-08-18 09:00:00,S001,P001,2,10,20,Cash
TX001,2026-08-18 10:00:00,S002,P002,3,10,30,Card"""

        result, message = self.app._evaluate_content_rules(
            "SALES_DATA_20260818090000.csv",
            csv_data,
            True
        )

        self.assertFalse(result)
        self.assertIn("Duplicate transaction_id", message)

    def test_non_numeric_values(self):
        csv_data = """transaction_id,timestamp,store_id,product_id,quantity,unit_price,total_amount,payment_method
TX001,2026-08-18 09:00:00,S001,P001,two,10,20,Cash"""

        result, message = self.app._evaluate_content_rules(
            "SALES_DATA_20260818090000.csv",
            csv_data,
            True
        )

        self.assertFalse(result)
        self.assertIn("Non-numeric", message)

    def test_invalid_positive_numbers(self):
        csv_data = """transaction_id,timestamp,store_id,product_id,quantity,unit_price,total_amount,payment_method
TX001,2026-08-18 09:00:00,S001,P001,0,10,0,Cash"""

        result, message = self.app._evaluate_content_rules(
            "SALES_DATA_20260818090000.csv",
            csv_data,
            True
        )

        self.assertFalse(result)
        self.assertIn("valid positive numbers", message)

    def test_incorrect_total_amount(self):
        csv_data = """transaction_id,timestamp,store_id,product_id,quantity,unit_price,total_amount,payment_method
TX001,2026-08-18 09:00:00,S001,P001,2,10,25,Cash"""

        result, message = self.app._evaluate_content_rules(
            "SALES_DATA_20260818090000.csv",
            csv_data,
            True
        )

        self.assertFalse(result)
        self.assertIn(
            "total_amount does not match calculation",
            message
        )

    def test_reconnects_and_retries_when_ftp_transfer_is_interrupted(self):
        filename = "SALES_DATA_20260818090000.csv"
        csv_data = (
            "transaction_id,timestamp,store_id,product_id,quantity,unit_price,"
            "total_amount,payment_method\n"
            "TX001,2026-08-18 09:00:00,S001,P001,2,10,20,Cash"
        ).encode("utf-8")
        stale_client = Mock()
        stale_client.retrbinary.side_effect = OSError("connection aborted")
        fresh_client = Mock()
        fresh_client.retrbinary.side_effect = (
            lambda command, callback: callback(csv_data)
        )

        self.app.selected_file = filename
        self.app.ftp_client = stale_client
        self.app.host_var = Mock()
        self.app.host_var.get.return_value = "127.0.0.1"
        self.app.user_var = Mock()
        self.app.user_var.get.return_value = "user"
        self.app.pass_var = Mock()
        self.app.pass_var.get.return_value = "password"
        self.app.status_var = Mock()
        self.app.connect_button = Mock()
        self.app.disconnect_button = Mock()

        with patch("sales_data.ftplib.FTP", return_value=fresh_client) as ftp_factory:
            result, message = self.app.validate_selected_file(silent=True)

        self.assertTrue(result)
        self.assertEqual(message, "Passed")
        stale_client.close.assert_called_once()
        ftp_factory.assert_called_once_with("127.0.0.1", timeout=5)
        fresh_client.login.assert_called_once_with(user="user", passwd="password")
        fresh_client.retrbinary.assert_called_once()
        self.assertIs(self.app.ftp_client, fresh_client)
        self.app.status_var.set.assert_called_with("Connected")

    def test_process_records_ftp_permission_error_for_error_logs(self):
        filename = "SALES_DATA_20260818090000.csv"
        self.app.selected_file = filename
        self.app.ftp_client = Mock()
        self.app.ftp_client.rename.side_effect = Exception("550 Permission denied")
        self.app.processor = SalesFileProcessor()
        self.app.validate_selected_file = Mock(return_value=(True, "Passed"))
        self.app._ensure_ftp_directory = Mock(return_value=True)
        self.app.refresh_file_list = Mock()

        with patch("sales_data.messagebox.showerror") as showerror:
            self.app.process_selected_file()

        self.assertEqual(len(self.app.processor.error_logs), 1)
        logged_filename, logged_error, _ = self.app.processor.error_logs[0]
        self.assertEqual(logged_filename, filename)
        self.assertIn("550 Permission denied", logged_error)
        self.assertIn("folder write permissions", logged_error)
        showerror.assert_called_once()


if __name__ == "__main__":
    unittest.main()