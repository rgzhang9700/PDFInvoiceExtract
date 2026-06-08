from abc import ABC, abstractmethod
from pathlib import Path
import re
import pandas as pd


_tax_lookup_cache = None
_supplier_lookup_cache = None


class BaseInvoiceParser(ABC):
    @abstractmethod
    def parse(self, text, *args, **kwargs):
        pass

    def lookup_tax_center_id(self, postcode):
        return lookup_tax_center_id(postcode)

    def lookup_company_code(self, supplier_name):
        return lookup_company_code(supplier_name)

    def _find_vendor_name(self, text):
        patterns = [
            r"(VALVOLINE(?:\s+INSTANT\s+OIL\s+CHANGE)?)",
            r"(jiffy\s*lube|jiffylube|jefflube)",
            r"(THE\s+CHARLES\s+MACHINE\s+WORKS)",
            r"(FLEETPRIDE)",
            r"(DITCH\s+WITCH)",
            r"(LES\s+SCHWAB)",
        ]

        for pattern in patterns:
            m = re.search(pattern, text or "", re.IGNORECASE)
            if m:
                vendor_name = m.group(1).upper()
                vendor_name = vendor_name.replace("JIFFYLUBE", "JIFFY LUBE")
                vendor_name = vendor_name.replace("JEFFLUBE", "JIFFY LUBE")
                return vendor_name

        return ""


def get_tax_lookup():
    global _tax_lookup_cache

    if _tax_lookup_cache is None:
        lookup_file = (
            Path(__file__).resolve().parent.parent.parent
            / "clients"
            / "northsky_comm"
            / "templates"
            / "TAXCenterLookup.xlsx"
        )

        if not lookup_file.exists():
            _tax_lookup_cache = {}
            return _tax_lookup_cache

        df = pd.read_excel(lookup_file, dtype=str)
        df.columns = [str(c).strip() for c in df.columns]

        _tax_lookup_cache = {}

        for _, row in df.iterrows():
            postcode = str(row.get("Postcode", "") or "").strip()
            taxcenterid = str(row.get("TaxCenterID", "") or "").strip()

            if postcode:
                postcode = postcode.split("-")[0]
                _tax_lookup_cache[postcode] = taxcenterid

    return _tax_lookup_cache


def lookup_tax_center_id(postcode):
    if not postcode:
        return ""

    postcode = str(postcode).strip().split("-")[0]
    return get_tax_lookup().get(postcode, "")


def get_supplier_lookup():
    global _supplier_lookup_cache

    if _supplier_lookup_cache is None:
        lookup_file = (
            Path(__file__).resolve().parent.parent.parent
            / "clients"
            / "northsky_comm"
            / "templates"
            / "SupplierLists.xlsx"
        )

        if not lookup_file.exists():
            _supplier_lookup_cache = {}
            return _supplier_lookup_cache

        df = pd.read_excel(
            lookup_file,
            sheet_name="SAPUI5 Export",
            dtype=str,
        )

        df.columns = [str(c).strip() for c in df.columns]

        _supplier_lookup_cache = {}

        for _, row in df.iterrows():
            supplier_name = str(row.get("Name of Supplier", "") or "").strip().upper()

            company_code = str(row.get("Company Code", "") or "").strip()
            supplier_code = str(row.get("Supplier", "") or "").strip()
            value = company_code or supplier_code

            if supplier_name:
                _supplier_lookup_cache[supplier_name] = value

    return _supplier_lookup_cache


def lookup_company_code(supplier_name):
    if not supplier_name:
        return ""

    supplier_name = str(supplier_name).strip().upper()
    lookup = get_supplier_lookup()

    if supplier_name in lookup:
        return lookup[supplier_name]

    for sap_name, company_code in lookup.items():
        if supplier_name in sap_name or sap_name in supplier_name:
            return company_code

    return ""
