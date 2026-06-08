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
        vendor_name = "FLEETPRIDE"
        ship_to_postcode = self._ship_to_zip_from_2col_text(text)

        return {
            "vendor_name": vendor_name,
            "Company_code": "V00096",
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

    # ------------------------------------------------------------
    # OCR box method: use right side under SHIP TO
    # ------------------------------------------------------------

    def _ship_to_zip_from_2col_text(self, text):
        text = text or ""
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

        # Find ZIP after state in right column only
        matches = list(re.finditer(r"\b[A-Z]{2}\s+(\d{5})(?:-\d{4})?\b", block, re.I))

        if matches:
            return matches[-1].group(1)

        return ""

    def _ship_to_zip_from_2col_text(self, text):
        text = text or ""

        # find SHIP TO only
        m = re.search(r"SHIP\s*TO", text, re.I)
        if not m:
            return ""

        # take small area after SHIP TO
        block = text[m.end():m.end() + 300]

        # stop before next section
        block = re.split(
            r"CHECK\s+NO|SHIPPER\s+NAME|PURCHASE\s+ORDER|REQUISITION|QUANTITY|PART\s+NUMBER|DESCRIPTION",
            block,
            maxsplit=1,
            flags=re.I,
        )[0]

        # find ZIP after state, example: CA 94536-6532
        matches = list(re.finditer(
            r"\b[A-Z]{2}\s+(\d{5})(?:-\d{4})?\b",
            block,
            re.I,
        ))

        if matches:
            return matches[-1].group(1)

        return ""

    # ------------------------------------------------------------
    # Other fields
    # ------------------------------------------------------------
 
    def _extract_invoice_date(self, text):
        text = text or ""
        for pattern in [r"INVOICE\s+DATE[\s\S]{0,120}?(\d{1,2}/\d{1,2})\s+(\d{2})\s+\d{6,}", 
                        r"INVOICE\s+DATE[\s\S]{0,40}?(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
                       ]:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(1)
        return ""
      
    def _extract_invoice_number(self, text):
        text = text or ""
        text = text.replace("\r", "\n")
        text = re.sub(r"[^\S\n]+", " ", text)
        for pattern in [r"\bINVOICE\s+NUMBER\b[\s\S]{0,120}?(\d{6,})", 
                        r"INVOICE\s+NO\.?\s*\n\s*\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\s+(\d+)",
                        r"\bINVOICE\b\s*(\d{6,})"
                       ]:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(1)
        return ""
        

    def _extract_balance_due(self, text):
        text = text or ""
        text = text.replace("\r", "\n")
        text = re.sub(r"[^\S\n]+", " ", text)
        text = re.sub(r"[sS](?=\d)", "$", text)
        text = re.sub(r"(\d)\s*[.]\s*(\d{2})\b", r"\1.\2", text)

        m = re.search(
            r"BALANCE\s+DUE[\s\S]{0,150}?[$]?\s*([0-9]{1,3}(?:,[0-9]{3})*|[0-9]+)\s*[.]\s*([0-9]{2})",
            text,
            re.I,
        )
        if m:
            return f"{m.group(1).replace(',', '')}.{m.group(2)}"

        return ""
