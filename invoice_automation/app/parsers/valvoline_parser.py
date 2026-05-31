import re
from datetime import datetime
from .base import BaseInvoiceParser
from .address_helpers import find_us_zip
from datetime import datetime

class ValvolineParser(BaseInvoiceParser):
    def parse(self, text):
        service_address = self._find_service_center_address(text)
        ship_to_address = self._find_ship_to_address(text)

        return {
            "vendor_name": "Valvoline",
            "vendor_address": service_address,
            "vendor_postcode": self._find_postcode(service_address),
            "ship_to_postcode": self._find_postcode(ship_to_address),
            "ship_to_address": ship_to_address,
            "service_center_address": service_address,
            "service_center_postcode": self._find_postcode(service_address),
            "invoice_number": self._find_invoice_number(text),
            "invoice_date": self._find_invoice_date(text),
            "amount": self._find_total(text),
            "po_number": self._find_po_number(text),
            "TAXCenterID": "",
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
                        return datetime.strptime(value, fmt).strftime("%m-%d-%y")
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
        m = re.search(
            r"VALVOLINE\s+INSTANT\s+OIL\s+CHANGE[\s\S]{0,300}?5020[\s\S]{0,100}?Corvallis,\s*OR\s*97333",
            text,
            re.IGNORECASE,
        )

        if m:
            return " ".join(m.group(0).split())

        return ""
    def _find_postcode(self, address):

        if not address:
            return ""

        matches = re.findall(r"\b\d{5}\b", address)

        if matches:
            return matches[-1]

        return ""
        
    def _find_ship_to_address(self, text):
        """
        Valvoline uses GUEST INFORMATION as the customer/ship-to address.
        """

        m = re.search(
            r"GUEST\s+INFORMATION\s+([\s\S]{0,200}?)(?:VEHICLE\s+INFORMATION|SERVICE\s+CENTER\s+INFORMATION)",
            text,
            re.IGNORECASE,
        )

        if m:
            return " ".join(m.group(1).split())

        return ""