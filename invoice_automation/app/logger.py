from pathlib import Path
import csv


SUCCESS_FIELDS = [
    "vendor_folder", "vendor_name", "vendor_address", "vendor_postcode",
    "ship_to_address", "ship_to_postcode", "service_center_address",
    "service_center_postcode", "invoice_number", "invoice_date", "amount",
    "po_number", "pdf_type", "pdf_file", "processed_file_path", "status", "error",
]

ERROR_FIELDS = ["vendor_folder", "pdf_file", "processed_file_path", "status", "error"]

SUMMARY_FIELDS = [
    "run_time", "vendor_folder", "total_files_found", "success_count",
    "failed_count", "duplicate_count", "total_invoice_files_processed",
]


class ProcessingLogger:
    def __init__(self, log_folder, logging_config):
        self.log_folder = Path(log_folder)
        self.log_folder.mkdir(parents=True, exist_ok=True)

        self.success_log = self.log_folder / logging_config.get("success_log", "success_log.csv")
        self.error_log = self.log_folder / logging_config.get("error_log", "error_log.csv")
        self.run_summary_log = self.log_folder / logging_config.get("run_summary_log", "run_summary.csv")

    def write_success(self, record):
        self._append_csv(self.success_log, SUCCESS_FIELDS, record)

    def write_error(self, record):
        self._append_csv(self.error_log, ERROR_FIELDS, record)

    def write_run_summary(self, record):
        self._append_csv(self.run_summary_log, SUMMARY_FIELDS, record)

    def _append_csv(self, file_path, fieldnames, record):
        file_exists = file_path.exists()

        with open(file_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow({field: record.get(field, "") for field in fieldnames})