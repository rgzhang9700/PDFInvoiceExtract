import re
from datetime import datetime
from .base import BaseInvoiceParser
from .address_helpers import find_us_zip


class ValvolineParser(BaseInvoiceParser):
    def parse(self, text):
        service_address = self._find_service_center_address(text)
        ship_to_address = self._find_ship_to_address(text)

        return {
            "vendor_name": "Valvoline",
            "vendor_address": service_address,
            "vendor_postcode": find_us_zip(service_address),
            "ship_to_address": ship_to_address,
            "ship_to_postcode": find_us_zip(ship_to_address),
            "service_center_address": service_address,
            "service_center_postcode": find_us_zip(service_address),
            "invoice_number": self._find_invoice_number(text),
            "invoice_date": self._find_invoice_date(text),
            "amount": self._find_total(text),
            "po_number": self._find_po_number(text),
        }

    def _find_invoice_number(self, text):
        for pattern in [r"Invoice\s+(\d+)", r"lnvoice\s+(\d+)", r"Invoice\s*#?\s*(\d+)"]:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(1)
        return ""

    def _find_invoice_date(self, text):
        patterns = [
            r"Invoice\s+\d+\s+(\d{1,2}/\d{1,2}/\d{4})",
            r"Invoice\s+\d+\s+(\d{1,2}/\d{1,2}/\d{2})",
            r"\b(\d{1,2}/\d{1,2}/\d{4})\b",
            r"\b(\d{1,2}/\d{1,2}/\d{2})\b",
        ]
        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                value = m.group(1)
                for fmt in ("%m/%d/%Y", "%m/%d/%y"):
                    try:
                        return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
                    except ValueError:
                        pass
        return ""

    def _find_total(self, text):
        for pattern in [r"\bTotal\s+([0-9,]+\.\d{2})", r"\bTotal\s+([0-9,]+)"]:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                value = matches[-1].replace(",", "")
                try:
                    return float(value)
                except ValueError:
                    return value
        return ""

    def _find_po_number(self, text):
        patterns = [
            r"PO IS VEHICLE FLEET#.*?(\d{4,})",
            r"Truck# on fender\s+.*?(\d{4,})",
            r"\bOR\s+([A-Za-z0-9]{4,})\b",
        ]
        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if m:
                return m.group(1)
        return ""

    def _find_service_center_address(self, text):
        lines = [x.strip() for x in text.splitlines() if x.strip()]
        for i, line in enumerate(lines):
            if "VALVOLINE INSTANT OIL CHANGE" in line.upper():
                return ", ".join(lines[i:i + 7])

        for i, line in enumerate(lines):
            if "PHILOMATH" in line.upper() or "CORVALLIS, OR 97333" in line.upper():
                return ", ".join(lines[max(0, i - 3):min(len(lines), i + 3)])

        return ""

    def _find_ship_to_address(self, text):
        lines = [x.strip() for x in text.splitlines() if x.strip()]
        for i, line in enumerate(lines):
            if "CUSTOMER INFORMATION" in line.upper() or "GUEST INFORMATION" in line.upper():
                return ", ".join(lines[i + 1:i + 7])

        for i, line in enumerate(lines):
            if "97330" in line or "97383" in line:
                return ", ".join(lines[max(0, i - 3):min(len(lines), i + 2)])

        return ""