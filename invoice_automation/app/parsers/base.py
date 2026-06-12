from abc import ABC, abstractmethod
from pathlib import Path
import re
import pandas as pd


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


def lookup_tax_center_id(postcode, lookup_file=None):
    """
    Look up TaxCenterID from TAXCenterLookup.xlsx by postcode.
    No module cache is used.
    """
    if not postcode:
        return ""

    postcode5 = re.sub(r"\D", "", str(postcode))[:5]
    if not postcode5:
        return ""

    lookup_file = Path(lookup_file) if lookup_file else _default_tax_lookup_file()
    if not lookup_file.exists():
        return ""

    try:
        df = pd.read_excel(lookup_file, dtype=str)
        df.columns = [str(c).strip() for c in df.columns]

        postcode_col = None
        tax_col = None

        for col in df.columns:
            col_key = col.strip().upper().replace(" ", "").replace("_", "")
            if col_key in ("POSTCODE", "ZIP", "ZIPCODE"):
                postcode_col = col
            if col_key in ("TAXCENTERID", "TAXCENTER"):
                tax_col = col

        if not postcode_col or not tax_col:
            return ""

        for _, row in df.iterrows():
            row_zip = re.sub(r"\D", "", str(row.get(postcode_col, "") or ""))[:5]
            if row_zip == postcode5:
                return str(row.get(tax_col, "") or "").strip()

    except Exception:
        return ""

    return ""


def lookup_company_code(supplier_name, lookup_file=None):
    """
    Look up Company Code from SupplierLists.xlsx by supplier/vendor name.
    No module cache is used.
    """
    if not supplier_name:
        return ""

    search_name = str(supplier_name).strip().upper()
    lookup_file = Path(lookup_file) if lookup_file else _default_supplier_lookup_file()
    if not lookup_file.exists():
        return ""

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

        if not supplier_col or not company_col:
            return ""

        # Exact match first.
        for _, row in df.iterrows():
            sap_name = str(row.get(supplier_col, "") or "").strip().upper()
            if sap_name == search_name:
                return str(row.get(company_col, "") or "").strip()

        # Partial match fallback.
        for _, row in df.iterrows():
            sap_name = str(row.get(supplier_col, "") or "").strip().upper()
            if sap_name and (search_name in sap_name or sap_name in search_name):
                return str(row.get(company_col, "") or "").strip()

    except Exception:
        return ""

    return ""


def lookup_supplier_code(supplier_name, lookup_file=None):
    """
    Look up SAP Supplier code from SupplierLists.xlsx by supplier/vendor name.

    Search order:
        1. VENDORS sheet
        2. Parsers sheet

    No SAPUI5 Export fallback.

    Example:
        VALVOLINE INSTANT OIL CHANGE -> V03884
        JIFFY LUBE -> V02305

    This is different from lookup_company_code():
        lookup_company_code() returns company code like 4600
        lookup_supplier_code() returns supplier/vendor code like V03884
    """
    if not supplier_name:
        return ""

    search_name = str(supplier_name).strip().upper()
    lookup_file = Path(lookup_file) if lookup_file else _default_supplier_lookup_file()
    if not lookup_file.exists():
        return ""

    def _find_from_sheet(sheet_name):
        try:
            df = pd.read_excel(lookup_file, sheet_name=sheet_name, dtype=str)
            df.columns = [str(c).strip() for c in df.columns]

            name_col = None
            supplier_col = None

            for col in df.columns:
                col_key = col.strip().upper().replace(" ", "").replace("_", "")

                if col_key in (
                    "VENDORNAME",
                    "VENDOR",
                    "NAMEOFSUPPLIER",
                    "SUPPLIERNAME",
                    "NAME",
                ):
                    name_col = col

                if col_key in (
                    "SUPPLIER",
                    "SUPPLIERCODE",
                    "SUPPLIERID",
                    "VENDORID",
                    "VENDORCODE",
                    "BUSINESSPARTNER",
                ):
                    supplier_col = col

            if not name_col or not supplier_col:
                return ""

            # Exact match first. Skip blank Supplier values.
            for _, row in df.iterrows():
                vendor_name = str(row.get(name_col, "") or "").strip().upper()
                supplier = str(row.get(supplier_col, "") or "").strip()

                if vendor_name == search_name and supplier:
                    return supplier

            # Partial match fallback. Skip blank Supplier values.
            for _, row in df.iterrows():
                vendor_name = str(row.get(name_col, "") or "").strip().upper()
                supplier = str(row.get(supplier_col, "") or "").strip()

                if vendor_name and supplier and (search_name in vendor_name or vendor_name in search_name):
                    return supplier

        except Exception:
            return ""

        return ""

    for sheet_name in ("VENDORS", "Parsers"):
        result = _find_from_sheet(sheet_name)
        if result:
            return result

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
        #text = text.replace("．", ".")
        text = text.replace("：", ":")
        text = text.replace("–", "-")
        text = text.replace("—", "-")
        text = text.replace("`", "'")

        # Common OCR fixes around labels.
        text = re.sub(r"(?i)invoice\s+date\s*/\s*time", "Invoice Date/Time", text)
        text = re.sub(r"(?i)invoice\s+date\s+invoice\s+no\.?,?", "INVOICE DATE INVOICE NO.", text)

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

    def lookup_supplier_code(self, supplier_name, lookup_file=None):
        return lookup_supplier_code(supplier_name, lookup_file=lookup_file)

    def _find_vendor_name(self, text):
        patterns = [
            r"(VALVOLINE(?:\s+INSTANT\s+OIL\s+CHANGE)?|\bDELTA\s+TRUCK\s+CENTER\b|HYDRAULIC CONTROLS|WAGNER-SMITH EQUIPMENT CO)",
            r"(jiffy\s*lube|jiffylube|jefflube)",
            r"(THE\s+CHARLES\s+MACHINE\s+WORKS|FLEETPRIDE|LES\s+SCHWAB|DITCH\s+WITCH(?:\s+WEST)?|NAPA)",
            r"(Randall\s+Creek\s+Sweeping|RDO\s+EQUIPMENT\s+CO|Continental Tire the Americas|PAPE\s+\n?MACHINERY|PAP[ÉE]\s+KENWORTH|TIPCO\s+TECHNOLOGIES)",
            r"(\bALTEC\b|\bAERIAL\b|linemen-tools\.com)",
        ]

        for pattern in patterns:
            m = re.search(pattern, text or "", re.IGNORECASE)
            if m:
                vendor_name = m.group(1).upper()
                vendor_name = vendor_name.replace("JIFFYLUBE", "JIFFY LUBE")
                vendor_name = vendor_name.replace("JEFFLUBE", "JIFFY LUBE")
                vendor_name = vendor_name.replace("PAPÉ KENWORTH", "PAPE KENWORTH NORTHWEST")
                return vendor_name

        return ""
