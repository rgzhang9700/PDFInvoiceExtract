import re
from datetime import datetime

from .base import BaseInvoiceParser


class LesSchwabParser(BaseInvoiceParser):
    """Parser for Les Schwab / LESHWEB invoice PDFs."""

    MONEY_PATTERN = (
        r"\$?\s*([0-9]{1,3}(?:\s*,\s*[0-9]{3})+\.\d{2}|"
        r"[0-9]{4,}\.\d{2}|[0-9]{1,3}\.\d{2})"
    )

    def parse(self, text):
        vendor_address = self._find_vendor_address(text)
        ship_to_address = self._find_ship_to_address(text)
        service_address = self._find_service_center_address(text) or vendor_address

        return {
            "vendor_name": "Les Schwab",
            "vendor_address": vendor_address,
            "vendor_postcode": self._find_postcode(vendor_address),
            "ship_to_address": ship_to_address,
            "ship_to_postcode": self._find_postcode(ship_to_address),
            "service_center_address": service_address,
            "service_center_postcode": self._find_postcode(service_address),
            "invoice_number": self._find_invoice_number(text),
            "invoice_date": self._find_invoice_date(text),
            "amount": self._find_total(text),
            "po_number": self._find_po_number(text),
            "TaxCenterID": "",
        }

    def _find_postcode(self, address):
        if not address:
            return ""

        state_zip = re.findall(r"\b[A-Z]{2}\s+(\d{5}(?:-\d{4})?)\b", address)
        if state_zip:
            return state_zip[-1]

        matches = re.findall(r"\b\d{5}(?:-\d{4})?\b", address)
        if matches:
            return matches[-1]

        return ""

    def _find_invoice_number(self, text):
        patterns = [
            r"\bInvoice\s*(?:No\.?|Number|#)\s*:?\s*([0-9]{6,})\b",
            r"\bInvoice\s+([0-9]{6,})\b",
            r"\bInv\s*(?:No\.?|#)?\s*:?\s*([0-9]{6,})\b",
            r"\b(668[0-9]{8})\b",
        ]

        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(1)

        return ""

    def _find_invoice_date(self, text):
        labeled_patterns = [
            r"\bInvoice\s*Date\b\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            r"\bDate\b\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            r"\bInv\s*Date\b\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b",
        ]

        for pattern in labeled_patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                parsed_date = self._format_date(m.group(1))
                if parsed_date:
                    return parsed_date

        word_date = re.search(
            r"\b([A-Z][a-z]{2,8}\s+\d{1,2},?\s+\d{4})\b",
            text,
            re.IGNORECASE,
        )
        if word_date:
            parsed_date = self._format_date(word_date.group(1))
            if parsed_date:
                return parsed_date

        return ""

    def _find_total(self, text):
        normalized = re.sub(r"[ \t]+", " ", text or "")
        total_patterns = [
            (
                rf"\b(?:Invoice\s+Total|Total\s+Invoice|Amount\s+Due|"
                rf"Balance\s+Due|Total\s+Due|Grand\s+Total|Total\s+Sale|"
                rf"Charges\s+This\s+Invoice|Total)\b\s*:?\s*{self.MONEY_PATTERN}"
            ),
            (
                rf"\b(?:Please\s+Pay|Pay\s+This\s+Amount|Amount\s+Payable)\b"
                rf"[\s\S]{{0,60}}?{self.MONEY_PATTERN}"
            ),
            rf"\b(?:Current\s+Charges|Net\s+Invoice)\b\s*:?\s*{self.MONEY_PATTERN}",
        ]

        for pattern in total_patterns:
            matches = re.findall(pattern, normalized, re.IGNORECASE)
            amounts = [self._to_float(match) for match in matches]
            amounts = [amount for amount in amounts if amount is not None]
            if amounts:
                return amounts[-1]

        return ""

    def _find_po_number(self, text):
        patterns = [
            r"\bP\.?\s*O\.?\s*(?:No\.?|Number|#)?\s*:?\s*([A-Za-z0-9/-]+)",
            r"\bPurchase\s+Order\s*(?:No\.?|#)?\s*:?\s*([A-Za-z0-9/-]+)",
        ]

        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(1)

        return ""

    def _find_vendor_address(self, text):
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        for i, line in enumerate(lines):
            if "LES SCHWAB" in line.upper():
                block = []
                for item in lines[i:i + 8]:
                    if any(
                        stop in item.upper()
                        for stop in ("BILL TO", "SHIP TO", "SOLD TO", "INVOICE")
                    ):
                        if block:
                            break
                    block.append(item)
                    if re.search(r"\b[A-Z]{2}\s+\d{5}(?:-\d{4})?\b", item):
                        break
                return ", ".join(block)

        return ""

    def _find_ship_to_address(self, text):
        return self._find_address_after_label(
            text,
            ("SHIP TO", "SOLD TO", "BILL TO"),
        )

    def _find_service_center_address(self, text):
        return self._find_address_after_label(
            text,
            ("STORE", "SERVICE CENTER", "LOCATION"),
        )

    def _find_address_after_label(self, text, labels):
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        stop_words = (
            "INVOICE", "ACCOUNT", "TERMS", "SALESPERSON", "QTY", "QUANTITY",
            "DESCRIPTION", "PART", "TOTAL", "AMOUNT", "DATE", "P.O", " PO ",
        )

        for i, line in enumerate(lines):
            clean_line = re.sub(r"[^A-Z0-9]", " ", line.upper())
            if any(label in clean_line for label in labels):
                block = []
                for item in lines[i + 1:i + 8]:
                    item_upper = item.upper()
                    if block and any(stop in item_upper for stop in stop_words):
                        break
                    block.append(item)
                    if re.search(r"\b[A-Z]{2}\s+\d{5}(?:-\d{4})?\b", item):
                        break
                if block:
                    return ", ".join(block)

        return ""

    def _format_date(self, value):
        clean_value = value.strip().replace("-", "/").replace(",", "")
        for fmt in ("%m/%d/%Y", "%m/%d/%y", "%B %d %Y", "%b %d %Y"):
            try:
                return datetime.strptime(clean_value, fmt).strftime("%m-%d-%y")
            except ValueError:
                pass
        return ""

    def _to_float(self, match):
        value = match[-1] if isinstance(match, tuple) else match
        try:
            return float(str(value).replace(" ", "").replace(",", ""))
        except ValueError:
            return None
