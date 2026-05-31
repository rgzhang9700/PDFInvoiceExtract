from abc import ABC, abstractmethod
from pathlib import Path
import pandas as pd

class BaseInvoiceParser(ABC):
    @abstractmethod
    def parse(self, text):
        pass
 
_tax_lookup_cache = None 

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
                _tax_lookup_cache[postcode] = taxcenterid

    return _tax_lookup_cache


def lookup_tax_center_id(postcode):

    if not postcode:
        return ""

    postcode = str(postcode).strip()

    # convert 95336-3208 -> 95336
    postcode = postcode.split("-")[0]

    return get_tax_lookup().get(postcode, "")



