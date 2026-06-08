import re
from datetime import datetime
from .base import BaseInvoiceParser, lookup_tax_center_id, lookup_company_code
from .address_helpers import find_us_zip
from datetime import datetime

class ValvolineParser(BaseInvoiceParser):
    def parse(self, text):
        service_address = self._find_service_center_address(text)
        ship_to_address = self._find_ship_to_address(text)
        vender_address = self._find_vendor_address(text)
        ship_to_postcode = self._find_postcode(ship_to_address)
        service_center_postcode =  self._find_postcode(service_address)
        vendor_postcode = self._find_postcode(vender_address)
        vendor_name = self._find_vendor_name(text)
        postcode_lookup = (ship_to_postcode or service_center_postcode or vendor_postcode)
        return {
            "vendor_name": vendor_name,
            "Company_code": lookup_company_code(vendor_name),
            "vendor_address": vender_address,
            "vendor_postcode": self._find_postcode(vender_address),
            "ship_to_postcode": self._find_postcode(ship_to_address),
            "ship_to_address": ship_to_address,
            "service_center_address": service_address,
            "service_center_postcode": self._find_postcode(service_address),
            "invoice_number": self._find_invoice_number(text),
            "invoice_date": self._find_invoice_date(text),
            "amount": self._find_total(text),
            "po_number": self._find_po_number(text),
            "TAXCenterID": lookup_tax_center_id(postcode_lookup),
        }

    def _find_vendor_name(self, text):
        patterns = [
            r"(VALVOLINE(?:\s+INSTANT\s+OIL\s+CHANGE)?)",
            r"(jiffy\s*lube|jiffylube|jefflube)",
            r"(THE\s+CHARLES\s+MACHINE\s+WORKS)",
        ]

        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(1).replace("jiffylube", "JIFFY LUBE")
        return ""
        
    def _find_invoice_number(self, text):
        for pattern in [r"Invoice\s+(\d+)", 
                        r"lnvoice\s+(\d+)", 
                        r"Invoice\s*#?\s*(\d+)", 
                        r"Invoice #\s*:\s+(\d+)",]:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(1)
        return ""

    def _find_invoice_date(self, text):
        patterns = [
            r"Invoice\s+\d+\s+(\d{1,2}/\d{1,2}/\d{4})",
            r"Date\s*:\s*(\d{2}/\d{2}/\d{4})",
        ]
  
        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                value = m.group(1)
                for fmt in ("%m/%d/%Y", "%m/%d/%y"):
                    try:
                        return datetime.strptime(value, fmt).strftime("%m/%d/%y")
                    except ValueError:
                        pass
        return ""

    def _find_total(self, text):
        for pattern in [r"\bTotal\s+([0-9,]+\.\d{2})",
                        r"\bTotal\s+([0-9,]+)",
                        r"Amount\s*due\s*[$8]?\s*([-\d,]+\.\d{2})",
                        r"Total\s+Amount\s+USD\s*\$?\s*([-\d,]+\.\d{2})"
                        ]:
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
            r"PO #.*?(\d{4,})",
        ]
        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if m:
                return m.group(1)
        return ""

    def _find_service_center_address(self, text):
        m = re.search(
            r"SERVICE\s+CENTER\s+INFORMATION([\s\S]+?)\b[A-Za-z .'-]+,\s*[A-Z]{2}\s+\d{5}\b",
            text,
            re.IGNORECASE,
        )

        if m:
            return " ".join(m.group(0).split())

        return ""
    def _find_postcode(self, address):
        if not address:
            return ""

        # Normal: CA 95336 or OR 97140-9563
        m = re.search(r"\b[A-Z]{2}\s+(\d{5})(?:-\d{4})?\b", address, re.I)
        if m:
            return m.group(1)

        # OCR merged ZIP: 953363208
        m = re.search(r"\b(\d{5})\d{4}\b", address)
        if m:
            return m.group(1)

        return ""
        
    def _find_ship_to_address(self, text):
        """
        Valvoline uses GUEST INFORMATION as the customer/ship-to address.
        """

        m = re.search(
            r"SHIP\s+TO:.*?(\d+\s+[A-Z0-9\s.#-]+).*?([A-Z\s]+\s+[A-Z]{2}\s+\d{5}(?:-\d{4})?)",
            text,
            re.IGNORECASE,
        )

        if m:
            return " ".join(m.group(1).split())

        return ""
        
    def _find_vendor_address(self, text):
        for pattern in [ r"(\d+\s+[A-Z0-9\s]+)\s+([A-Z\s]+,\s*CA\s*\d{5})",
                          r"(?:jiffy\s*lube|jiffylube|jefflube)[\s\S]*?(\d+\s+[^\n]+)[\s\S]*?([A-Z\s]+,\s*[A-Z]{2}\s*\d{5,9})",
        ]:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(2)
        return ""
