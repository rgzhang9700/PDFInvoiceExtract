from abc import ABC, abstractmethod
from pathlib import Path
import pandas as pd


class BaseInvoiceParser(ABC):
    @abstractmethod
    def parse(self, text):
        pass


_tax_lookup_cache = None
_supplier_lookup_cache = None


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

        df = pd.read_excel(lookup_file, dtype=str)
        df.columns = [str(c).strip() for c in df.columns]

        _tax_lookup_cache = {}

        for _, row in df.iterrows():
            postcode = str(row.get("Postcode", "")).strip()
            taxcenterid = str(row.get("TaxCenterID", "")).strip()

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

        df = pd.read_excel(
            lookup_file,
            sheet_name="SAPUI5 Export",
            dtype=str
        )

        df.columns = [str(c).strip() for c in df.columns]

        _supplier_lookup_cache = {}

        for _, row in df.iterrows():
            supplier_name = str(row.get("Name of Supplier", "")).strip().upper()
            company_code = str(row.get("Company Code", "")).strip()

            if supplier_name:
                _supplier_lookup_cache[supplier_name] = company_code

    return _supplier_lookup_cache


def lookup_company_code(supplier_name):
    if not supplier_name:
        return ""

    supplier_name = str(supplier_name).strip().upper()
    lookup = get_supplier_lookup()

    # Exact match
    if supplier_name in lookup:
        return lookup[supplier_name]

    # Partial match
    for sap_name, company_code in lookup.items():
        if supplier_name in sap_name or sap_name in supplier_name:
            return company_code


def lookup_tax_center_id(postcode):

    if not postcode:
        return ""

    postcode = str(postcode).strip()

    # convert 95336-3208 -> 95336
    postcode = postcode.split("-")[0]

    return get_tax_lookup().get(postcode, "")


    _supplier_lookup = None

    @classmethod
    def load_supplier_lookup(cls):
        if cls._supplier_lookup is None:
            df = pd.read_excel(
                "SupplierLists.xlsx",
                sheet_name="SAPUI5 Export",
                dtype=str
            )

            cls._supplier_lookup = {
                str(row["Name of Supplier"]).strip().upper():
                str(row["Supplier"]).strip()
                for _, row in df.iterrows()
            }

  
    def lookup_company_code(self, supplier_name):
        if not supplier_name:
            return None

        self.load_supplier_lookup()

        supplier_name = supplier_name.strip().upper()

        # Exact match
        if supplier_name in self._supplier_lookup:
            return self._supplier_lookup[supplier_name]

        # Partial match
        for sap_name, company_code in self._supplier_lookup.items():
            if supplier_name in sap_name or sap_name in supplier_name:
                return company_code

        return None