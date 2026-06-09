from abc import ABC, abstractmethod
from pathlib import Path
import re
import pandas as pd


_tax_lookup_cache = None
_supplier_lookup_cache = None


def _project_root():
    """
    base.py is expected at: app/parsers/base.py
    Project root is two levels up from app/parsers.
    """
    return Path(__file__).resolve().parents[2]


def _default_tax_lookup_file():
    return _project_root() / "clients" / "northsky_comm" / "templates" / "TAXCenterLookup.xlsx"


def _default_supplier_lookup_file():
    return _project_root() / "clients" / "northsky_comm" / "templates" / "SupplierLists.xlsx"


def get_tax_lookup(lookup_file=None):
    """
    Load postcode -> TaxCenterID lookup from TAXCenterLookup.xlsx.
    This is a module-level function so parsers can import it from .base.
    """
    global _tax_lookup_cache

    lookup_file = Path(lookup_file) if lookup_file else _default_tax_lookup_file()
    cache_key = str(lookup_file.resolve()) if lookup_file.exists() else str(lookup_file)

    if _tax_lookup_cache is None or _tax_lookup_cache.get("__file__") != cache_key:
        lookup = {"__file__": cache_key}

        if not lookup_file.exists():
            _tax_lookup_cache = lookup
            return lookup

        try:
            df = pd.read_excel(lookup_file, dtype=str)
            df.columns = [str(c).strip() for c in df.columns]

            # Accept common column spellings.
            postcode_col = None
            tax_col = None
            for col in df.columns:
                col_key = col.strip().upper().replace(" ", "").replace("_", "")
                if col_key in ("POSTCODE", "ZIP", "ZIPCODE"):
                    postcode_col = col
                if col_key in ("TAXCENTERID", "TAXCENTER"):
                    tax_col = col

            if postcode_col and tax_col:
                for _, row in df.iterrows():
                    postcode = str(row.get(postcode_col, "") or "").strip()
                    taxcenterid = str(row.get(tax_col, "") or "").strip()

                    if postcode:
                        postcode5 = re.sub(r"\D", "", postcode)[:5]
                        if postcode5:
                            lookup[postcode5] = taxcenterid

        except Exception:
            # Keep parser from crashing if lookup file has issue.
            pass

        _tax_lookup_cache = lookup

    return _tax_lookup_cache


def lookup_tax_center_id(postcode, lookup_file=None):
    """
    Public function imported by parser files.
    Example:
        from .base import lookup_tax_center_id
    """
    if not postcode:
        return ""

    postcode5 = re.sub(r"\D", "", str(postcode))[:5]
    if not postcode5:
        return ""

    lookup = get_tax_lookup(lookup_file=lookup_file)
    return lookup.get(postcode5, "")


def get_supplier_lookup(lookup_file=None):
    """
    Load supplier name -> Company Code lookup from SupplierLists.xlsx.
    Sheet expected: SAPUI5 Export
    Common columns:
        Name of Supplier
        Company Code
    """
    global _supplier_lookup_cache

    lookup_file = Path(lookup_file) if lookup_file else _default_supplier_lookup_file()
    cache_key = str(lookup_file.resolve()) if lookup_file.exists() else str(lookup_file)

    if _supplier_lookup_cache is None or _supplier_lookup_cache.get("__file__") != cache_key:
        lookup = {"__file__": cache_key}

        if not lookup_file.exists():
            _supplier_lookup_cache = lookup
            return lookup

        try:
            df = pd.read_excel(lookup_file, sheet_name="SAPUI5 Export", dtype=str)
            df.columns = [str(c).strip() for c in df.columns]

            supplier_col = None
            company_col = None
            for col in df.columns:
                col_key = col.strip().upper().replace(" ", "").replace("_", "")
                if col_key in ("NAMEOFSUPPLIER", "SUPPLIERNAME", "VENDORNAME", "NAME"):
                    supplier_col = col
                if col_key in ("COMPANYCODE", "COMPANY"):
                    company_col = col

            if supplier_col and company_col:
                for _, row in df.iterrows():
                    supplier_name = str(row.get(supplier_col, "") or "").strip().upper()
                    company_code = str(row.get(company_col, "") or "").strip()
                    if supplier_name:
                        lookup[supplier_name] = company_code

        except Exception:
            # Keep parser from crashing if lookup file has issue.
            pass

        _supplier_lookup_cache = lookup

    return _supplier_lookup_cache


def lookup_company_code(supplier_name, lookup_file=None):
    """
    Public function imported by parser files.
    Looks up company code by supplier/vendor name.
    """
    if not supplier_name:
        return ""

    supplier_name = str(supplier_name).strip().upper()
    lookup = get_supplier_lookup(lookup_file=lookup_file)

    # Exact match
    if supplier_name in lookup:
        return lookup[supplier_name]

    # Partial match
    for sap_name, company_code in lookup.items():
        if sap_name == "__file__":
            continue
        if supplier_name in sap_name or sap_name in supplier_name:
            return company_code

    return ""


class BaseInvoiceParser(ABC):
    @abstractmethod
    def parse(self, text):
        pass

    def _clean_ocr_text(self, text):
        """
        Clean OCR/PDF text but keep line breaks.
        Use this for address/block parsing where line breaks still help.
        """
        text = text or ""

        # Normalize weird spaces and punctuation from OCR/PDF extraction.
        text = text.replace("\xa0", " ")
        text = text.replace("\t", " ")
        text = text.replace("，", ",")
        text = text.replace("．", ".")
        text = text.replace("：", ":")
        text = text.replace("–", "-")
        text = text.replace("—", "-")
        text = text.replace("`", "'")

        # Common OCR fixes around labels.
        text = re.sub(r"(?i)invoice\s+date\s*/\s*time", "Invoice Date/Time", text)
        text = re.sub(r"(?i)invoice\s+date\s+invoice\s+no\.?", "INVOICE DATE INVOICE NO.", text)

        # Fix OCR money false reads only when directly before a digit.
        # Example: s1,148.98 -> $1,148.98
        text = re.sub(r"(?i)\b[sS](?=\d)", "$", text)

        # Normalize spaces but keep newlines.
        text = re.sub(r"[ \r\f\v]+", " ", text)
        text = re.sub(r" *\n *", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

    def _clean_ocr_one_line(self, text):
        """
        Clean OCR/PDF text and collapse everything to one line.
        Use this for regex searches for invoice number/date/amount.
        """
        text = self._clean_ocr_text(text)
        return re.sub(r"\s+", " ", text).strip()

    def _normalize_date(self, value, output_format="%m/%d/%Y"):
        """
        Normalize dates like 5-31-26, 05/29/2026, 05-29-2026.
        """
        from datetime import datetime

        value = str(value or "").strip()
        if not value:
            return ""

        value = value.replace("-", "/")

        for fmt in ("%m/%d/%Y", "%m/%d/%y"):
            try:
                return datetime.strptime(value, fmt).strftime(output_format)
            except ValueError:
                pass

        return ""

    def _extract_first(self, text, patterns, flags=re.IGNORECASE):
        """
        Try multiple regex patterns and return group(1) from the first match.
        """
        text = text or ""
        for pattern in patterns:
            m = re.search(pattern, text, flags)
            if m:
                return m.group(1).strip()
        return ""

    # Optional instance wrappers, in case any parser calls self.lookup_...
    def lookup_tax_center_id(self, postcode, lookup_file=None):
        return lookup_tax_center_id(postcode, lookup_file=lookup_file)

    def lookup_company_code(self, supplier_name, lookup_file=None):
        return lookup_company_code(supplier_name, lookup_file=lookup_file)

    def _find_vendor_name(self, text):
        patterns = [
            r"(VALVOLINE(?:\s+INSTANT\s+OIL\s+CHANGE)?)",
            r"(jiffy\s*lube|jiffylube|jefflube)",
            r"(THE\s+CHARLES\s+MACHINE\s+WORKS)",
            r"(FLEETPRIDE)",
            r"(DITCH\s+WITCH(?:\s+WEST)?)",
            r"(LES\s+SCHWAB)",
            r"(TIPCO\s+TECHNOLOGIES)",
        ]

        for pattern in patterns:
            m = re.search(pattern, text or "", re.IGNORECASE)
            if m:
                vendor_name = m.group(1).upper()
                vendor_name = vendor_name.replace("JIFFYLUBE", "JIFFY LUBE")
                vendor_name = vendor_name.replace("JEFFLUBE", "JIFFY LUBE")
                return vendor_name

        return ""
