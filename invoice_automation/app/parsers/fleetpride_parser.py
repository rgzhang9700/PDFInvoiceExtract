import re
from .base import BaseInvoiceParser, lookup_tax_center_id, lookup_company_code


class FleetPrideParser(BaseInvoiceParser):
    """
    Simple FleetPride parser.

    This version removes separate _clean_text() and _norm() helper functions.

    SHIP TO ZIP rule:
        Find SHIP TO row
        Split next few rows into 2 columns
        Use right column only
        Return last ZIP after state
    """

    def parse(self, text, ocr_results=None, image_width=None, image_height=None, source_path=None):
        text = text or ""
        vendor_name = self._find_vendor_name(text)
        ship_to_postcode = self._ship_to_zip_from_2col_text(text)

        return {
            "vendor_name": vendor_name,
            "Company_code":  lookup_company_code(vendor_name),
            "vendor_address": "",
            "vendor_postcode": "",
            "ship_to_address": "",
            "ship_to_postcode": ship_to_postcode,
            "invoice_number": self._extract_invoice_number(text),
            "invoice_date": self._extract_invoice_date(text),
            "amount": self._extract_balance_due(text),
            "CompanyCode": lookup_company_code(vendor_name),
            "TAXCenterID": lookup_tax_center_id(ship_to_postcode),
        }
        
    def _ship_to_zip_from_2col_text(self, text):
        lines = text.splitlines()

        right_text = []

        for line in lines:
            # Only lines around SOLD TO / SHIP TO block
            if "SOLD TO" in line.upper() and "SHIP TO" in line.upper():
                parts = re.split(r"\s{4,}", line)
                if len(parts) >= 2:
                    right_text.append(parts[-1])
                continue

            # Split each visual row into left/right column
            parts = re.split(r"\s{4,}", line)

            if len(parts) >= 2:
                right_text.append(parts[-1])

        block = " ".join(right_text)
        print (block)

        # Find ZIP after state in right column only
        matches = list(re.finditer(r"\b[A-Z]{2}\s+(\d{5})(?:-\d{4})?\b", block, re.I))

        if matches:
            return matches[-1].group(1)

        return ""

    # ------------------------------------------------------------
    # Other fields
    # ------------------------------------------------------------
 
    def _extract_invoice_date(self, text):
        # Case 1: normal date, like 05/27/26
        patterns = [r"INVOICE\s+DATE[\s\S]{0,150}?(\d{1,2}/\d{1,2}/\d{2,4})",
                    r"INVOICE\s+DATE\s+INVOICE\s+NO\.?\s+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\s+\d{5,}",
                   ]
        
        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(1)

        # Case 2: split date, like 05/27 then 26 then invoice number
        m = re.search(
            r"INVOICE\s+DATE[\s\S]{0,150}?(\d{1,2}/\d{1,2})\s+(\d{2,4})\s+\d{6,}",
            text,
            re.I,
        )
        if m:
            return f"{m.group(1)}/{m.group(2)}"

        return ""
      
    def _extract_invoice_number(self, text):
        for pattern in [r"\bINVOICE\s+NUMBER\b[\s\S]{0,120}?(\d{6,})", 
                        r"INVOICE\s+NO\.?\s*\n\s*\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\s+(\d+)",
                        r"\bINVOICE\b\s*(\d{6,})",
                        r"INVOICE\s+DATE\s+INVOICE\s+NO\.?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
                       ]:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(1)
        return ""
        

    def _extract_balance_due(self, text):
        for pattern in [r"PLEASE\s+PAY\s*>?\s*THIS\s+TOTAL\s*>?\s*([0-9,]+\.\d{2})", 
                        r"PLEASE\s+PAY[\s\S]{0,120}?([0-9][0-9,\s]*[.]\s*\d\s*\d)",
                        r"BALANCE\s+DUE[\s\S]{0,80}?\$?\s*([0-9][0-9,\s]*\.\s*\d{2})"
                       ]:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(1).replace(",", "").replace(" ", "")
        return ""
       
