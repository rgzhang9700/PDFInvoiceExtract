from pathlib import Path
import sqlite3
import json
from datetime import datetime
import hashlib


class InvoiceHistory:
    def __init__(self, database_file):
        self.database_file = Path(database_file)
        self.database_file.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.database_file)

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS invoice_history (
                    invoice_key TEXT PRIMARY KEY,
                    vendor_folder TEXT,
                    invoice_number TEXT,
                    invoice_date TEXT,
                    amount TEXT,
                    pdf_file TEXT,
                    created_at TEXT,
                    payload_json TEXT
                )
            """)

    def make_invoice_key(self, vendor_folder, invoice_number, amount, invoice_date, pdf_file=""):
        """
        FIX:
        Include pdf_file in the key.

        Old key:
            vendor|invoice_number|invoice_date|amount

        Problem:
            If OCR misses invoice_number/date/amount, multiple files can all become:
            OILVANDOR|||
            and then only the first invoice is processed.

        New key:
            vendor|invoice_number|invoice_date|amount|pdf_file

        This prevents 3 PDFs from becoming only 2 records.
        """

        raw_key = f"{vendor_folder}|{invoice_number}|{invoice_date}|{amount}|{pdf_file}"

        # Keep key short and safe.
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def exists(self, invoice_key):
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT 1 FROM invoice_history WHERE invoice_key = ?",
                (invoice_key,)
            )
            return cur.fetchone() is not None

    def add(self, invoice_key, invoice):
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO invoice_history (
                    invoice_key, vendor_folder, invoice_number, invoice_date,
                    amount, pdf_file, created_at, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    invoice_key,
                    invoice.get("vendor_folder", ""),
                    invoice.get("invoice_number", ""),
                    str(invoice.get("invoice_date", "")),
                    str(invoice.get("amount", "")),
                    invoice.get("pdf_file", ""),
                    datetime.now().isoformat(timespec="seconds"),
                    json.dumps(invoice, default=str),
                )
            )