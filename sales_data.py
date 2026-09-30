import datetime
import csv
import io
import re
import urllib.request
import json
import uuid
import ftplib
import tkinter as tk
from typing import Callable
from tkinter import ttk
from tkinter import messagebox


APP_TITLE = "Sales Data Validation System - Secure File Management"

THEME = {
    "app_bg": "#ececea",
    "header_bg": "#2f4358",
    "header_text": "white",
    "section_bg": "#deddd8",
    "primary": "#0b8f91",
    "primary_hover": "#0a7779",
    "disabled": "#d0d0d0",
    "danger": "#bb3333",
    "muted": "#777777",
}

FONT = "Segoe UI"
MONO_FONT = "Consolas"


class SalesFileProcessor:
    def __init__(self):
        self.default_files = []
        self.error_logs = []
        self._error_log_observers = []

    def add_error_log_observer(
        self,
        observer: Callable[[str, str, str], None],
    ):
        if observer not in self._error_log_observers:
            self._error_log_observers.append(observer)

    def remove_error_log_observer(
        self,
        observer: Callable[[str, str, str], None],
    ):
        if observer in self._error_log_observers:
            self._error_log_observers.remove(observer)

    def add_default_file(self, filename):
        if filename not in self.default_files:
            self.default_files.append(filename)

    def add_error_log(self, filename, error_message):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.error_logs.append((filename, error_message, timestamp))
        for observer in tuple(self._error_log_observers):
            observer(filename, error_message, timestamp)


class SalesDataProcessorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1280x900")
        self.minsize(1050, 700)

        self.ftp_client = None
        self.all_files = []
        self.selected_file = None
        self.processor = SalesFileProcessor()

        self.host_var = tk.StringVar(value="127.0.0.1")
        self.user_var = tk.StringVar(value="")
        self.pass_var = tk.StringVar(value="")
        self.search_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Disconnected")
        self.connection_var = tk.StringVar(value="")
        self.file_count_var = tk.StringVar(value="Files: 0")
        self.selection_var = tk.StringVar(value="No file selected")

        self._build_style()
        self._build_ui()
        self.processor.add_error_log_observer(self._on_error_log_added)
        self.log_message("System", "Ready.")

    def _build_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("Header.TFrame", background=THEME["header_bg"])
        style.configure("Header.TLabel", background=THEME["header_bg"], foreground=THEME["header_text"], font=(FONT, 20, "bold"))
        style.configure("HeaderStatus.TLabel", background=THEME["header_bg"], foreground=THEME["header_text"], font=(FONT, 12, "bold"))
        style.configure("Section.TLabelframe", background=THEME["section_bg"])
        style.configure("Section.TLabelframe.Label", font=(FONT, 10, "bold"))
        style.configure("Action.TButton", font=(FONT, 10), padding=(12, 8))
        style.configure("Primary.TButton", background=THEME["primary"], foreground=THEME["header_text"], font=(FONT, 10, "bold"), padding=(14, 8))
        style.map("Primary.TButton", background=[("active", THEME["primary_hover"]), ("disabled", THEME["disabled"])])
        self.configure(background=THEME["app_bg"])

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, style="Header.TFrame", padding=(14, 10))
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Sales Data Validation System", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(header, textvariable=self.status_var, style="HeaderStatus.TLabel").grid(row=0, column=1, sticky="e")

        top = ttk.Frame(self, padding=(8, 0))
        top.grid(row=1, column=0, sticky="nsew")
        top.rowconfigure(0, weight=1)
        top.columnconfigure(1, weight=1)
        top.columnconfigure(2, weight=2)

        self._build_connection_panel(top).grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._build_server_panel(top).grid(row=0, column=1, sticky="nsew", padx=(0, 8))
        self._build_logs_panel(top).grid(row=0, column=2, sticky="nsew")

    def _build_connection_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="Server Connection", padding=12, style="Section.TLabelframe")
        for row, label in enumerate(("FTP Host", "Username", "Password")):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=5)

        ttk.Entry(frame, textvariable=self.host_var, width=28).grid(row=0, column=1, sticky="ew", pady=5)
        ttk.Entry(frame, textvariable=self.user_var, width=28).grid(row=1, column=1, sticky="ew", pady=5)
        ttk.Entry(frame, textvariable=self.pass_var, width=28, show="*").grid(row=2, column=1, sticky="ew", pady=5)

        buttons = ttk.Frame(frame)
        buttons.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.connect_button = ttk.Button(buttons, text="Connect", style="Primary.TButton", command=self.connect_to_ftp)
        self.disconnect_button = ttk.Button(buttons, text="Disconnect", command=self.disconnect_from_ftp, state=tk.DISABLED)
        self.connect_button.grid(row=0, column=0, padx=(0, 6))
        self.disconnect_button.grid(row=0, column=1)

        ttk.Label(frame, textvariable=self.connection_var, foreground=THEME["danger"]).grid(row=4, column=0, columnspan=2, sticky="w", pady=(14, 0))
        frame.columnconfigure(1, weight=1)
        return frame

    def _build_server_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="Server Files", padding=12, style="Section.TLabelframe")
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(2, weight=1)

        ttk.Label(frame, text="Search:").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.search_var).grid(row=0, column=1, sticky="ew", padx=(8, 6))
        ttk.Button(frame, text="Search", command=self.execute_search).grid(row=0, column=2, padx=2)
        ttk.Button(frame, text="Clear", command=self.clear_search).grid(row=0, column=3, padx=2)

        ttk.Label(frame, text="Available Files:").grid(row=1, column=0, columnspan=4, sticky="w", pady=(14, 4))

        list_frame = ttk.Frame(frame)
        list_frame.grid(row=2, column=0, columnspan=4, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        self.file_list = tk.Listbox(list_frame, height=14, activestyle="dotbox")
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.file_list.yview)
        self.file_list.configure(yscrollcommand=scrollbar.set)
        self.file_list.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.file_list.bind("<<ListboxSelect>>", self.on_file_selected)

        ttk.Label(frame, textvariable=self.selection_var, foreground=THEME["muted"]).grid(row=3, column=0, columnspan=4, sticky="e", pady=(8, 4))

        action_row = ttk.Frame(frame)
        action_row.grid(row=4, column=0, columnspan=4, sticky="ew")
        for col in range(4):
            action_row.columnconfigure(col, weight=1)

        self.validate_button = ttk.Button(action_row, text="Validate", command=self.validate_selected_file, state=tk.DISABLED)
        self.process_button = ttk.Button(action_row, text="Process", command=self.process_selected_file, state=tk.DISABLED)
        self.validate_button.grid(row=0, column=0, sticky="ew", padx=4)
        self.process_button.grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(action_row, text="Error Logs", command=self.display_error_logs).grid(row=0, column=2, sticky="ew", padx=4)
        ttk.Button(action_row, text="Stats", command=self.show_stats).grid(row=0, column=3, sticky="ew", padx=4)
        ttk.Label(frame, textvariable=self.file_count_var, font=(FONT, 10, "bold")).grid(row=5, column=3, sticky="e", pady=(14, 0))
        return frame

    def _build_logs_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="Activity Logs", padding=10, style="Section.TLabelframe")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        log_area = ttk.Frame(frame)
        log_area.grid(row=0, column=0, sticky="nsew")
        log_area.rowconfigure(0, weight=1)
        log_area.columnconfigure(0, weight=1)
        self.activity_text = tk.Text(log_area, wrap="word", height=30, font=(MONO_FONT, 10), relief="solid", borderwidth=1)
        scroll = ttk.Scrollbar(log_area, orient=tk.VERTICAL, command=self.activity_text.yview)
        self.activity_text.configure(yscrollcommand=scroll.set)
        self.activity_text.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        button_row = ttk.Frame(frame)
        button_row.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        button_row.columnconfigure(0, weight=1)
        ttk.Button(button_row, text="Clear Logs", command=self.clear_logs).grid(row=0, column=0, sticky="ew")
        return frame

    def connect_to_ftp(self):
        server = self.host_var.get().strip()
        user = self.user_var.get().strip()
        password = self.pass_var.get()

        if not server:
            messagebox.showwarning("Warning", "Please enter an FTP Server IP address.")
            return

        try:
            self.log_message("System", f"Attempting to connect to FTP server at {server}...")
            self.ftp_client = ftplib.FTP(server, timeout=5)
            self.ftp_client.login(user=user, passwd=password)

            self._set_ftp_connection_state(True)
            self.log_message("Success", "FTP Connection established successfully!")
            self.refresh_file_list()
        except Exception as exc:
            self.log_message("Error", f"Connection failed: {exc}")
            messagebox.showerror("FTP Connection Error", f"Could not connect to the FTP server.\nError: {exc}")

    def _set_ftp_connection_state(self, connected):
        self.status_var.set("Connected" if connected else "Disconnected")
        self.connect_button.configure(state=tk.DISABLED if connected else tk.NORMAL)
        self.disconnect_button.configure(state=tk.NORMAL if connected else tk.DISABLED)

    def _reconnect_to_ftp(self):
        previous_client = self.ftp_client
        self.ftp_client = None
        self._set_ftp_connection_state(False)

        if previous_client:
            try:
                previous_client.close()
            except OSError:
                pass

        client = ftplib.FTP(self.host_var.get().strip(), timeout=5)
        try:
            client.login(
                user=self.user_var.get().strip(),
                passwd=self.pass_var.get(),
            )
        except Exception:
            try:
                client.close()
            except OSError:
                pass
            raise

        self.ftp_client = client
        self._set_ftp_connection_state(True)
        self.log_message("Success", "FTP connection restored.")

    def disconnect_from_ftp(self):
        if self.ftp_client:
            try:
                self.ftp_client.quit()
            except Exception:
                pass
            self.ftp_client = None
            self.status_var.set("Disconnected")
            self.connect_button.configure(state=tk.NORMAL)
            self.disconnect_button.configure(state=tk.DISABLED)
            self.clear_file_list()
            self.all_files.clear()
            self.selected_file = None
            self.selection_var.set("No file selected")
            self.file_count_var.set("Files: 0")
            self._set_file_actions(False)
            self.log_message("System", "Disconnected from FTP Server.")
        else:
            messagebox.showinfo("Status", "No active connection is currently running.")

    def refresh_file_list(self):
        if not self.ftp_client:
            self.all_files = []
            self.populate_file_list(self.all_files)
            self.file_count_var.set("Files: 0")
            return

        try:
            raw_files = []
            self.ftp_client.retrlines("NLST", raw_files.append)
            self.all_files = [filename for filename in raw_files if filename not in ("main", "errors", ".", "..")]
            self.populate_file_list(self.all_files)
            self.file_count_var.set(f"Files: {len(self.all_files)}")
            self.log_message("System", f"Loaded {len(self.all_files)} files from Server directory.")
        except Exception as exc:
            self.log_message("Error", f"Failed to retrieve files: {exc}")

    def populate_file_list(self, file_list):
        self.clear_file_list()
        for filename in file_list:
            self.file_list.insert(tk.END, filename)

    def clear_file_list(self):
        self.file_list.delete(0, tk.END)
        self.selected_file = None
        self.selection_var.set("No file selected")
        self._set_file_actions(False)

    def execute_search(self):
        query = self.search_var.get().strip().lower()

        if not query:
            messagebox.showwarning("Search Warning", "Please type a file name keyword to search.")
            return

        matching_files = [filename for filename in self.all_files if query in filename.lower()]

        if not matching_files:
            messagebox.showerror("Error", "Not exist file")
            self.log_message("Warning", f"Search failed for key: '{query}' - File not found.")
        else:
            self.populate_file_list(matching_files)
            self.file_count_var.set(f"Files: {len(matching_files)}")
            self.log_message("Search", f"Found {len(matching_files)} matching file(s) for keyword: '{query}'")

    def clear_search(self):
        self.search_var.set("")
        self.populate_file_list(self.all_files)
        self.file_count_var.set(f"Files: {len(self.all_files)}")

    def on_file_selected(self, _event):
        selection = self.file_list.curselection()
        if not selection:
            return
        self.selected_file = self.file_list.get(selection[0])
        self.selection_var.set(self.selected_file)
        self._set_file_actions(True)

    def _set_file_actions(self, enabled):
        state = tk.NORMAL if enabled else tk.DISABLED
        self.validate_button.configure(state=state)
        self.process_button.configure(state=state)

    def validate_selected_file(self, silent=False):
        if not self.selected_file:
            if not silent:
                messagebox.showwarning("Validation Warning", "Please select a file from the list to validate.")
            return False, "No file selected"

        filename = self.selected_file
        if not silent:
            self.log_message("Validation", f"Starting evaluation for: {filename}")

        pattern = r"^SALES_DATA_\d{14}\.csv$"
        if not re.match(pattern, filename):
            msg = f"Rejected: Incorrectly formatted filename or unsupported file extension '{filename}'."
            if not silent:
                self.log_message("Rejected", msg)
                self.processor.add_error_log(filename, msg)
                messagebox.showerror("Validation Failed", msg)
            return False, msg

        if not self.ftp_client:
            msg = "FTP connection is inactive."
            if not silent:
                self.log_message("System", "Cannot validate. Offline state active.")
                messagebox.showinfo("Simulated State", "Connect to a real live local FTP server.")
            return False, msg

        try:
            memory_stream = io.BytesIO()
            try:
                self.ftp_client.retrbinary(f"RETR {filename}", memory_stream.write)
            except (OSError, EOFError) as exc:
                self.log_message("Warning", f"FTP transfer interrupted; reconnecting and retrying once: {exc}")
                self._reconnect_to_ftp()
                memory_stream = io.BytesIO()
                self.ftp_client.retrbinary(f"RETR {filename}", memory_stream.write)
            file_bytes = memory_stream.getvalue()

            if len(file_bytes) == 0:
                msg = f"Rejected: File '{filename}' is empty (0-byte size)."
                if not silent:
                    self.log_message("Rejected", msg)
                    messagebox.showerror("Validation Failed", msg)
                return False, msg

            text_data = file_bytes.decode("utf-8")
        except Exception as exc:
            if isinstance(exc, (OSError, EOFError)) and self.ftp_client:
                try:
                    self.ftp_client.close()
                except OSError:
                    pass
                self.ftp_client = None
                self._set_ftp_connection_state(False)
            msg = f"Rejected: Decoding/FTP error - {exc}"
            if not silent:
                self.log_message("Rejected", msg)
                messagebox.showerror("Validation Failed", msg)
            return False, msg

        return self._evaluate_content_rules(filename, text_data, silent)

    def _evaluate_content_rules(self, filename, text_content, silent):
        expected_headers = [
            "transaction_id", "timestamp", "store_id", "product_id",
            "quantity", "unit_price", "total_amount", "payment_method"
        ]

        try:
            reader = csv.reader(io.StringIO(text_content))
            rows = list(reader)

            if not rows or len(rows) < 1:
                raise ValueError("No header sequence matrix found.")

            actual_headers = rows[0]
            if actual_headers != expected_headers:
                raise ValueError("Missing or incorrectly named headers.")

            transaction_ids = set()

            for idx, row in enumerate(rows[1:], start=2):
                if len(row) != len(expected_headers):
                    raise ValueError(f"Line {idx}: Column constraint mismatch.")

                tx_id, timestamp, store_id, prod_id, qty_str, price_str, total_str, pay_method = row

                if not all(field.strip() for field in row):
                    raise ValueError(f"Line {idx}: Empty cell value discovered.")

                if tx_id in transaction_ids:
                    raise ValueError(f"Line {idx}: Duplicate transaction_id '{tx_id}'.")
                transaction_ids.add(tx_id)

                try:
                    quantity = float(qty_str)
                    unit_price = float(price_str)
                    total_amount = float(total_str)
                except ValueError:
                    raise ValueError(f"Line {idx}: Non-numeric quantity/price/total values.")

                if quantity <= 0 or unit_price <= 0 or total_amount <= 0:
                    raise ValueError(f"Line {idx}: Values must contain valid positive numbers.")

                if abs((quantity * unit_price) - total_amount) > 0.01:
                    raise ValueError(f"Line {idx}: total_amount does not match calculation.")

            if not silent:
                self.log_message("Success", f"File '{filename}' validated successfully!")
                messagebox.showinfo("Validation Success", f"File '{filename}' Successfully validated.")
            return True, "Passed"
        except ValueError as err:
            if not silent:
                self.log_message("Rejected", f"Rejected: {err}")
                messagebox.showerror("Validation Failed", f"Rejected: {err}")
            return False, str(err)

    def _ensure_ftp_directory(self, folder_name):
        try:
            self.ftp_client.cwd(folder_name)
            self.ftp_client.cwd("..")
            return True
        except Exception:
            try:
                self.ftp_client.mkd(folder_name)
                self.log_message("System", f"Created folder '{folder_name}' on FTP Server.")
                return True
            except Exception as exc:
                self.log_message("Error", f"Could not create folder '{folder_name}': {exc}")
                return False

    def _get_api_uuid(self):
        try:
            url = "https://www.uuidtools.com/api/generate/v1"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                if isinstance(data, list) and len(data) > 0:
                    return data[0]
        except Exception as exc:
            self.log_message("Warning", f"External API failed: {exc}. Falling back to local UUID generator.")
        return str(uuid.uuid1())

    def process_selected_file(self):
        if not self.selected_file:
            messagebox.showwarning("Process Warning", "Please select a file from the list to process.")
            return

        if not self.ftp_client:
            messagebox.showerror("Processing Failed", "Connect to the FTP server first.")
            return

        filename = self.selected_file
        self.log_message("Processing", f"Processing file: {filename}...")

        is_valid, status_msg = self.validate_selected_file(silent=True)

        if is_valid:
            if not self._ensure_ftp_directory("main"):
                msg = "Could not access or create the /main folder. Check FTP folder permissions."
                self.processor.add_error_log(filename, msg)
                messagebox.showerror("FTP Error", msg)
                self.refresh_file_list()
                return
            try:
                self.ftp_client.rename(filename, f"main/{filename}")
                self.processor.add_default_file(f"main/{filename}")
                self.log_message("Processed", f"SUCCESS: '{filename}' processed and stored under '/main' folder.")
                messagebox.showinfo("Process Complete", f"'{filename}' processed successfully and stored under '/main'!")
            except Exception as exc:
                msg = f"Could not move valid file to /main folder. Check FTP rename and folder write permissions.\nError: {exc}"
                self.log_message("Error", msg)
                self.processor.add_error_log(filename, msg)
                messagebox.showerror("FTP Error", msg)
        else:
            if not self._ensure_ftp_directory("errors"):
                msg = "Could not access or create the /errors folder. Check FTP folder permissions."
                self.processor.add_error_log(filename, f"{status_msg}; {msg}")
                messagebox.showerror("FTP Error", msg)
                self.refresh_file_list()
                return
            new_uuid = self._get_api_uuid()
            error_filename = f"{new_uuid}.csv"

            try:
                self.ftp_client.rename(filename, f"errors/{error_filename}")
                self.processor.add_error_log(error_filename, status_msg)
                self.log_message("Error Logged", f"FAILED: '{filename}' has errors. Stored as 'errors/{error_filename}'.")
                messagebox.showerror("Process Failed", f"'{filename}' failed validation!\nStored in /errors folder as:\n{error_filename}")
            except Exception as exc:
                msg = f"Could not move rejected file to /errors folder. Check FTP rename and folder write permissions.\nError: {exc}"
                self.log_message("Error", msg)
                self.processor.add_error_log(filename, f"{status_msg}; {msg}")
                messagebox.showerror("FTP Error", msg)

        self.refresh_file_list()

    def display_error_logs(self):
        logs = self.processor.error_logs
        if not logs:
            messagebox.showinfo("Error Logs", "No files have encountered errors yet!")
            return

        log_summary = "--- Categorized OOP Error Logs ---\n\n"
        for idx, (fname, err, ts) in enumerate(logs, 1):
            log_summary += f"{idx}. File: {fname}\n   At: {ts}\n   Reason: {err}\n\n"

        top = tk.Toplevel(self)
        top.title("Stored Error Logs")
        top.geometry("600x400")

        text = tk.Text(top, wrap="word", font=(FONT, 10))
        text.insert("1.0", log_summary)
        text.config(state="disabled")
        text.pack(fill="both", expand=True, padx=10, pady=10)

    def _on_error_log_added(self, filename, error_message, _timestamp):
        self.log_message("Error Log", f"Recorded '{filename}': {error_message}")

    def show_stats(self):
        messagebox.showinfo(
            "File Stats",
            f"Visible files: {self.file_list.size()}\n"
            f"Total loaded files: {len(self.all_files)}",
        )

    def show_help(self):
        help_text = (
            "How it Works:\n\n"
            "1. Connect to your FTP Server.\n"
            "2. Select a file from the server directory.\n"
            "3. Click 'Process'.\n"
            "   - Clean/Safe files are moved under `/main` folder.\n"
            "   - Files with issues are renamed with external UUIDs and stored under `/errors` folder.\n"
            "4. Use the buttons to view errors or clear logs."
        )
        messagebox.showinfo("Help / Guide", help_text)

    def clear_logs(self):
        self.activity_text.delete("1.0", tk.END)
        self.log_message("System", "Log panel cleared.")

    def log_message(self, log_type, message):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        self.activity_text.insert(tk.END, f"[{now}] {log_type}: {message}\n")
        self.activity_text.see(tk.END)


if __name__ == "__main__":
    app = SalesDataProcessorApp()
    app.mainloop()
