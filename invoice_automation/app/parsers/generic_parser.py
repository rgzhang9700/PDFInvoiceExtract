import re
from datetime import datetime
from .base import BaseInvoiceParser
from .address_helpers import find_address_near_keyword, find_first_city_state_zip_block


class GenericParser(BaseInvoiceParser):
    def parse(self, text):
        vendor_address, vendor_postcode = find_first_city_state_zip_block(text)
        ship_to_address, ship_to_postcode = find_address_near_keyword(text, "SHIP TO")
        service_address, service_postcode = find_address_near_keyword(text, "SERVICE CENTER")

        return {
            "vendor_name": self._find_vendor_name(text),
            "vendor_address": vendor_address,
            "vendor_postcode": vendor_postcode,
            "ship_to_address": ship_to_address,
            "ship_to_postcode": ship_to_postcode,
            "service_center_address": service_address,
            "service_center_postcode": service_postcode,
            "invoice_number": self._find_invoice_number(text),
            "invoice_date": self._find_invoice_date(text),
            "amount": self._find_total(text),
            "po_number": self._find_po_number(text),
        }

    def _find_vendor_name(self, text):
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return lines[0] if lines else "Unknown"

    def _find_invoice_number(self, text):
        patterns = [
            r"Invoice\s*#?\s*:?\s*([A-Za-z0-9\-]+)",
            r"Inv\s*#?\s*:?\s*([A-Za-z0-9\-]+)",
            r"Invoice Number\s*[:#]?\s*([A-Za-z0-9\-]+)",
        ]
        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(1)
        return ""

    def _find_invoice_date(self, text):
        patterns = [r"(\d{1,2}/\d{1,2}/\d{4})", r"(\d{4}-\d{2}-\d{2})"]
        for pattern in patterns:
            m = re.search(pattern, text)
            if m:
                value = m.group(1)
                for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
                    try:
                        return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
                    except ValueError:
                        pass
        return ""

    def _find_total(self, text):
        patterns = [
            r"Total\s*\$?\s*([0-9,]+\.\d{2})",
            r"Amount Due\s*\$?\s*([0-9,]+\.\d{2})",
            r"Balance Due\s*\$?\s*([0-9,]+\.\d{2})",
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                return float(matches[-1].replace(",", ""))
        return ""

    def _find_po_number(self, text):
        patterns = [
            r"PO\s*#?\s*:?\s*([A-Za-z0-9\-]+)",
            r"Purchase Order\s*#?\s*:?\s*([A-Za-z0-9\-]+)",
        ]
        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(1)
        return ""