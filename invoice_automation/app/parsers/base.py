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

def extract_vendor_invoice_from_filename(file_path):
    """
    Extract vendor_name and invoice_number from filenames like:
        JGP PETERBILT INV # 65915SMX1.pdf
        LANDMARK FORD INV # 4089005.pdf
        INTERSTATE BATTERY 120029722.pdf
    """
    filename = Path(file_path).stem.strip()
    filename = re.sub(r"\s+", " ", filename)

    patterns = [
        r"^(.+?)\s+INV\s*#?\s*([A-Z0-9.-]{5,})(?:\s.*)?$",
        r"^(.+?)\s+([A-Z0-9.-]{6,})(?:\s.*)?$",
        r"^\s*(.+?)\s+((?:INV\s*)?\d[\w.-]*)\s*\.pdf$", #Romain
    ]

    for pattern in patterns:
        m = re.fullmatch(pattern, filename, re.IGNORECASE)
        if not m:
            continue

        vendor_name = re.sub(r"\s+", " ", m.group(1)).strip().upper()
        invoice_number = m.group(2).strip().upper()

        # Do not allow blank/generic vendor name
        if not vendor_name or vendor_name in ("INV", "INVOICE"):
            continue

        return {
            "vendor_name": vendor_name,
            "invoice_number": invoice_number,
        }

    return {
        "vendor_name": "",
        "invoice_number": "",
    }

def _normalize_excel_key(value):
    """Normalize Excel sheet/column names for case-insensitive lookup."""
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def _read_excel_sheet_case_insensitive(lookup_file, sheet_names, dtype=str):
    """
    Read the first existing sheet from sheet_names, ignoring case/spaces.
    Example: "VENDORS", "Vendors", and "vendors" all match.
    """
    lookup_file = Path(lookup_file)
    xls = pd.ExcelFile(lookup_file)

    wanted = {_normalize_excel_key(name): name for name in sheet_names}
    for actual_sheet in xls.sheet_names:
        actual_key = _normalize_excel_key(actual_sheet)
        if actual_key in wanted:
            df = pd.read_excel(lookup_file, sheet_name=actual_sheet, dtype=dtype)
            df.columns = [str(c).strip() for c in df.columns]
            return df, actual_sheet

    return None, ""



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



def _get_exact(row, column_name):
    """Return a clean string from an exact Excel column name."""
    value = row.get(column_name, "")
    if pd.isna(value):
        return ""
    return str(value or "").strip()


def _blank_supplier_info():
    return {
        "Supplier": "",
        "Parser": "",
        "GLAccount": "",
        "ItemText": "",
        "Payee": "",
        "Company Code": "",
        "matched_name": "",
        "source_sheet": "",

        # lower-case aliases for easier use in other files
        "supplier": "",
        "vendor_id": "",
        "parser": "",
        "gl_account": "",
        "item_text": "",
        "payee": "",
        "company_code": "",
    }


def _sync_supplier_aliases(info):
    """Keep exact Excel keys and lower-case aliases in sync."""
    info["supplier"] = info.get("Supplier", "")
    info["vendor_id"] = info.get("Supplier", "")
    info["parser"] = info.get("Parser", "")
    info["gl_account"] = info.get("GLAccount", "")
    info["item_text"] = info.get("ItemText", "")
    info["payee"] = info.get("Payee", "")
    info["company_code"] = info.get("Company Code", "")
    return info


def _match_rows_by_name(df, name_column, search_name):
    """
    Match rows by an exact column name.
    Exact match first, then partial match.
    """
    if name_column not in df.columns:
        return []

    exact_matches = []
    partial_matches = []

    for _, row in df.iterrows():
        row_name = _get_exact(row, name_column)
        row_name_upper = row_name.upper()

        if not row_name_upper:
            continue

        if row_name_upper == search_name:
            exact_matches.append(row)
        elif search_name in row_name_upper or row_name_upper in search_name:
            partial_matches.append(row)

    return exact_matches + partial_matches


def lookup_company_code(supplier_name, lookup_file=None):
    """
    Look up Company Code from SupplierLists.xlsx using the VENDORS sheet only.

    Exact sheet/column names used:
        Sheet: VENDORS
        Columns: Name of Supplier, Company Code

    """
    if not supplier_name:
        return ""

    search_name = str(supplier_name).strip().upper()
    lookup_file = Path(lookup_file) if lookup_file else _default_supplier_lookup_file()
    if not lookup_file.exists():
        return ""

    try:
        df, actual_sheet = _read_excel_sheet_case_insensitive(lookup_file, ("VENDORS",), dtype=str)
        if df is None:
            return ""

        if "Name of Supplier" not in df.columns or "Company Code" not in df.columns:
            return ""

        for row in _match_rows_by_name(df, "Name of Supplier", search_name):
            company_code = _get_exact(row, "Company Code")
            if company_code:
                return company_code

    except Exception:
        return ""

    return ""


def lookup_supplier_code(supplier_name, lookup_file=None):
    """
    Look up supplier details from SupplierLists.xlsx.

    Uses exact sheet/column names only.

    VENDORS sheet columns:
        Name of Supplier
        Supplier
        Company Code

    Parsers sheet columns:
        VendorName
        Supplier
        Parser
        GLAccount
        ItemText
        Payee

    Returns a dictionary, not just a string:
        info = lookup_supplier_code("JIFFY LUBE")
        info["Supplier"]
        info["Parser"]
        info["GLAccount"]
        info["ItemText"]
        info["Payee"]
        info["Company Code"]
    """
    info = _blank_supplier_info()

    if not supplier_name:
        return info

    search_name = str(supplier_name).strip().upper()
    lookup_file = Path(lookup_file) if lookup_file else _default_supplier_lookup_file()
    if not lookup_file.exists():
        return info

    try:
        # 1. Try VENDORS sheet first for Supplier and Company Code.
        vendors_df, vendors_sheet = _read_excel_sheet_case_insensitive(lookup_file, ("VENDORS",), dtype=str)
        if vendors_df is not None:
            required_vendor_cols = {"Name of Supplier", "Supplier", "Company Code"}
            if required_vendor_cols.issubset(set(vendors_df.columns)):
                vendor_rows = _match_rows_by_name(vendors_df, "Name of Supplier", search_name)
                if vendor_rows:
                    row = vendor_rows[0]
                    info["Supplier"] = _get_exact(row, "Supplier")
                    info["Company Code"] = _get_exact(row, "Company Code")
                    info["matched_name"] = _get_exact(row, "Name of Supplier")
                    info["source_sheet"] = vendors_sheet or "VENDORS"

        # 2. Look in Parsers sheet for Parser, GLAccount, ItemText, Payee.
        #    If Supplier was not found in VENDORS, Parsers can also provide Supplier.
        parsers_df, parsers_sheet = _read_excel_sheet_case_insensitive(lookup_file, ("Parsers",), dtype=str)
        if parsers_df is not None:
            required_parser_cols = {"VendorName", "Supplier", "Parser", "GLAccount", "ItemText", "Payee"}
            if required_parser_cols.issubset(set(parsers_df.columns)):
                parser_rows = _match_rows_by_name(parsers_df, "VendorName", search_name)
                if parser_rows:
                    row = parser_rows[0]

                    parser_supplier = _get_exact(row, "Supplier")
                    if parser_supplier:
                        info["Supplier"] = parser_supplier

                    info["Parser"] = _get_exact(row, "Parser")
                    info["GLAccount"] = _get_exact(row, "GLAccount")
                    info["ItemText"] = _get_exact(row, "ItemText")
                    info["Payee"] = _get_exact(row, "Payee")

                    if not info.get("matched_name"):
                        info["matched_name"] = _get_exact(row, "VendorName")
                    if not info.get("source_sheet"):
                        info["source_sheet"] = parsers_sheet or "Parsers"
                    elif parsers_sheet:
                        info["source_sheet"] = f'{info["source_sheet"]}+{parsers_sheet}'

    except Exception:
        return _sync_supplier_aliases(info)

    return _sync_supplier_aliases(info)


class BaseInvoiceParser(ABC):
    @abstractmethod
    def parse(self, text, file_path=None):
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


    def extract_vendor_invoice_from_filename(self, file_path):
        return extract_vendor_invoice_from_filename(file_path)

    def _find_vendor_name(self, text):
        patterns = [
            r"(VALVOLINE(?:\s+INSTANT\s+OIL\s+CHANGE)?|\bDELTA\s+TRUCK\s+CENTER\b|HYDRAULIC CONTROLS|WAGNER-SMITH EQUIPMENT CO)",
            r"(jiffy\s*lube|jiffylube|jefflube|Continental\s+Tire\s+the\s+Americas|\bDITCH\s+WITCH\s+OF\s+CENTRAL\s+TEXAS\b)",
            r"(THE\s+CHARLES\s+MACHINE\s+WORKS|FLEETPRIDE|LES\s+SCHWAB|Ditch\s+Witch\s+West|NAPA|Canby\s+Signs)",
            r"(Randall\s+Creek\s+Sweeping|RDO\s+EQUIPMENT\s+CO|PAPE\s+\n?MACHINERY|PAP[ÉE]\s+KENWORTH|TIPCO\s+TECHNOLOGIES)",
            r"(\bALTEC\b|\bAERIAL\b|linemen-tools\.com|ROMAINE ELECTRIC)",
            r"(MODESTO\s+WELD(?:ING\s+PRODUCTS)?|\bPETERSON\b|\bRDO\b|RDO\s+EQUIPMENT\s+CO)",
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
