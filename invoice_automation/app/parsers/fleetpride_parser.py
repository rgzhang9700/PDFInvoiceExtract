import re
from .base import BaseInvoiceParser, lookup_tax_center_id, lookup_company_code, lookup_supplier_code
from datetime import datetime

class FleetPrideParser(BaseInvoiceParser):
    def parse(self, text, ocr_results=None, image_width=None, image_height=None, source_path=None):
        raw_text = text or ""
        clean_text = self._clean_ocr_text(raw_text)
        text = self._clean_ocr_one_line(raw_text)

        vendor_name = self._find_vendor_name(text)
        if not vendor_name and re.search(r"\bWHITE\s+CAP\b", text, re.I):
            vendor_name = "WHITE CAP"
        if not vendor_name and re.search(r"\bRDO\s+EQUIPMENT\b", text, re.I):
            vendor_name = "RDO EQUIPMENT CO"
        if not vendor_name and re.search(r"\bPAP[ÉE]\s+MACHINERY\b", text, re.I):
            vendor_name = "PAPE MACHINERY"

        ship_to_postcode = self._ship_to_zip_from_2col_text(raw_text) or self._extract_ship_to_postcode(text)

        invoice_number = self._extract_invoice_number(text)
        invoice_date = self._extract_invoice_date(text)

        # Continental/FleetPride format:
        # ORDER DATE ... BILLING DATE NUMBER
        # 06 09 26 ... 06 08 26 5055242618
        continental_date, continental_number = self._find_continental_invoice_date_number(text)

        if not invoice_number:
            invoice_number = continental_number

        if not invoice_date:
            invoice_date = continental_date

        return {
            "vendor_name": vendor_name,
            "vendor_id":  lookup_supplier_code(vendor_name),
            "vendor_address": "",
            "vendor_postcode": "",
            "ship_to_address": "",
            "ship_to_postcode": ship_to_postcode,
            "invoice_number": invoice_number,
            "invoice_date": invoice_date,
            "amount": self._extract_balance_due(text),
            "CompanyCode": lookup_company_code(vendor_name),
            "TAXCenterID": lookup_tax_center_id(ship_to_postcode),
        }

    def _ship_to_zip_from_2col_text(self, text):
        lines = (text or "").splitlines()

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

    def _extract_ship_to_postcode(self, text):
        text = text or ""

        # White Cap format:
        # SHIP TO: 10001463062 SHERWOOD YARD 10860 SW CLUTTER ROAD SHERWOOD OR 97140
        m = re.search(
            r"SHIP\s+TO\s*:?[\s\S]{0,160}?\b[A-Z]{2}\s+(\d{5})(?:-\d{4})?\b",
            text,
            re.I,
        )
        if m:
            return m.group(1)

        # General fallback: last ZIP in text
        matches = list(re.finditer(r"\b[A-Z]{2}\s+(\d{5})(?:-\d{4})?\b", text, re.I))
        if matches:
            return matches[-1].group(1)

        return ""

    # ------------------------------------------------------------
    # Other fields
    # ------------------------------------------------------------

    def _extract_invoice_date(self, text):
        text = text or ""

        patterns = [
            r"INVOICE\s+DATE[\s\S]{0,160}?(\d{1,2}/\d{1,2}/\d{2,4})", #White Cap
            r"INVOICE\s+DATE\s+INVOICE\s+NO\.?[\s\S]{0,60}?(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\s+\d{6,}",#PAPE
            r"INVOICE\s+DATE\s+INVOICE\s+NO\.?\s+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\s+\d{5,}", #FleetPride
            r"(\d{1,2}/\d{1,2}/\d{2,4})\s+\d{1,2}:\d{2}:\d{2}[\s\S]{0,120}?P\d{6,}", #RDO
            r"\bDate\b[\s\S]{0,80}?(\d{1,2}/\d{1,2}/\d{2,4})", #ALTEC
            r"Invoice\s+Date[\s\S]{0,120}?(\d{1,2}/\d{1,2}/\d{2,4})",  # DELTA TRUCK CENTER
        ]

        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(1)

        # FleetPride split date, like 05/27 then 26 then invoice number
        m = re.search(
            r"INVOICE\s+DATE[\s\S]{0,150}?(\d{1,2}/\d{1,2})\s+(\d{2,4})\s+\d{6,}",
            text,
            re.I,
        )
        if m:
            return f"{m.group(1)}/{m.group(2)}"

        return datetime.now().strftime("%m/%d/%Y")

    def _extract_invoice_number(self, text):
        text = text or ""

        patterns = [
            r"INVOICE\s+NUMBER\s+(\d{6,})",# White Cap format: INVOICE NUMBER 50033132660
            r"Invoice\s+No\.?:?\s*(\d{5,})", #Altec
            r"INVOICE\s+DATE\s+INVOICE\s+NO\.?[\s\S]{0,60}?\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\s+(\d{6,})",  # PAPE / Ditch Witch style
            r"\bInvoice\b[\s\S]{0,80}?([A-Z]\d{6,}:\d{2})",  # DELTA TRUCK CENTER
            r"\bINVOICE\s+NUMBER\b[\s\S]{0,120}?(\d{6,})", # FleetPride
            r"\bINVOICE\s+NO\.?[\s\S]{0,80}?(\d{6,})",
            r"\b(P\d{6,})\b",# RDO
            r"Invoice\s*#\s*:?\s*([A-Z0-9-]+)", #WAGNER
        ]

        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(1)
        return ""

    def _find_continental_invoice_date_number(self, text):
        text = text or ""
        clean_text = re.sub(r"\s+", " ", text).strip()

        # Continental format:
        # ORDER DATE ... BILLING DATE NUMBER
        # 06 09 26 ... 06 08 26 5055242618
        matches = re.findall(
            r"(\d{2})\s+(\d{2})\s+(\d{2})\s+(\d{6,})",
            clean_text,
            re.IGNORECASE,
        )

        if matches:
            mm, dd, yy, invoice_number = matches[-1]
            invoice_date = f"{mm}/{dd}/{yy}"
            return invoice_date, invoice_number

        return "", ""

    def _extract_balance_due(self, text):
        for pattern in [
            r"TOTAL\s+INVOICE\s+([0-9,]+\.\s*\d{2})",  # White Cap
            r"Total\s+Due\s+([0-9,]+\.\s*\d{2})",  # Continental
            r"BALANCE\s+DUE[\s\S]{0,80}?[$S8]?\s*([0-9][0-9,\s]*\.\s*\d{2})",  # FleetPride
            r"\bTOTAL\b\s+([0-9,]+\s+\d{2})",  # PAPE: TOTAL / 63 / 15
            r"TOTAL\s+DUE\s+RDO\s+([0-9,]+\.\s*\d{2})",  # RDO
            r"Invoice\s+total\s+([0-9,]+\.\s*\d{2})", #ALTEC
            r"\bTotal\s*:\s*([0-9,]+\.\s*\d{2})",  # DELTA TRUCK CENTER final total
            r"AMOUNT\s+DUE\s*[$S8]?\s*([0-9,]+\.\d{2})", #HYDRAULIC CONTROLS
            r"\bTotal\s*[$S8]?\s*([0-9,]+\.\d{2})", #RANDLL CREEK
        ]:
            matches = re.findall(pattern, text or "", re.IGNORECASE)

            if matches:
                value = matches[-1]

                if isinstance(value, tuple):
                    value = next((v for v in value if v), "")

                value = str(value)
                value = value.replace(",", "")
                value = value.replace(" ", "")
                value = value.replace("$", "")
                value = value.replace("S", "")
                value = value.replace("s", "")

                # PAPE OCR can read TOTAL / 63 / 15 as "63 15".
                # After removing spaces above it becomes "6315", so fix before float.
                if re.fullmatch(r"\d{3,}", value) and pattern.startswith(r"\bTOTAL\b"):
                    value = value[:-2] + "." + value[-2:]

                try:
                    return round(float(value), 2)
                except ValueError:
                    continue

        return round(float("100"), 2)
