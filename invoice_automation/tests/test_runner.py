import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from app import runner


class StaticParser:
    def parse(self, _text):
        return {
            "invoice_number": "INV-1",
            "invoice_date": "2026-06-01",
            "amount": "100.00",
        }


class RunnerTests(unittest.TestCase):
    def test_parse_vendor_folder_processes_every_invoice_without_duplicate_history(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            client_root = Path(tmpdir)
            input_folder = client_root / "incoming"
            input_folder.mkdir()
            (input_folder / "invoice-a.pdf").write_bytes(b"pdf")
            (input_folder / "invoice-b.pdf").write_bytes(b"pdf")

            logger = Mock()

            with (
                patch.object(runner, "extract_pdf_text", return_value=("invoice text", "digital")),
                patch.object(runner, "detect_parser", return_value=StaticParser()),
            ):
                invoices, successful_records, failed_records, summary = runner.parse_vendor_folder(
                    vendor_folder="OILVENDOR",
                    vendor_config={"input_folder": "./incoming", "parser": "generic"},
                    processing_config={},
                    client_root=client_root,
                    logger=logger,
                )

        self.assertEqual(len(invoices), 2)
        self.assertEqual(len(successful_records), 2)
        self.assertEqual(failed_records, [])
        self.assertEqual(summary["total_files_found"], 2)
        self.assertEqual(summary["failed_count"], 0)
        self.assertNotIn("duplicate_count", summary)
        self.assertTrue(all(invoice["status"] == "parsed_waiting_for_excel" for invoice in invoices))
        logger.write_error.assert_not_called()


if __name__ == "__main__":
    unittest.main()
