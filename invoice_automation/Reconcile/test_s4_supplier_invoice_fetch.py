#!/usr/bin/env python3
"""
Simple test script: fetch SAP S/4HANA Supplier Invoice by Reference.

Purpose:
  Test whether your SAP S/4HANA OData API can find a supplier invoice
  where SAP field "Reference" equals your vendor invoice number.

Default SAP API:
  /sap/opu/odata/sap/API_SUPPLIERINVOICE_PROCESS_SRV/A_SupplierInvoice

Common OData field for SAP screen field "Reference":
  ReferenceDocument

If your SAP metadata uses another field name, change REFERENCE_FIELD below.

Install:
  pip install requests pandas openpyxl

Set environment variables in Windows CMD:
  set SAP_BASE_URL=https://your-sap-host
  set SAP_USER=your_user
  set SAP_PASSWORD=your_password

Run:
  py test_s4_supplier_invoice_fetch.py --reference 351331095

Run with a different reference field:
  py test_s4_supplier_invoice_fetch.py --reference 351331095 --reference-field Reference

Run and save result:
  py test_s4_supplier_invoice_fetch.py --reference 351331095 --out sap_invoice_test.xlsx
"""

import argparse
import os
import sys
from pathlib import Path

import requests
import pandas as pd


DEFAULT_SERVICE_PATH = "/sap/opu/odata/sap/API_SUPPLIERINVOICE_PROCESS_SRV/A_SupplierInvoice"
DEFAULT_REFERENCE_FIELD = "ReferenceDocument"


def build_url(base_url: str, service_path: str) -> str:
    return base_url.rstrip("/") + "/" + service_path.lstrip("/")


def get_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"ERROR: Missing environment variable: {name}")
        return ""
    return value


def extract_odata_results(data: dict):
    """
    Handles common SAP OData V2 and V4 JSON shapes.
    V2: {"d": {"results": [...]}}
    V4: {"value": [...]}
    """
    if isinstance(data, dict):
        if "d" in data:
            d = data["d"]
            if isinstance(d, dict) and "results" in d:
                return d["results"]
            if isinstance(d, dict):
                return [d]

        if "value" in data and isinstance(data["value"], list):
            return data["value"]

    return []


def fetch_supplier_invoice_by_reference(
    base_url: str,
    user: str,
    password: str,
    reference_value: str,
    service_path: str = DEFAULT_SERVICE_PATH,
    reference_field: str = DEFAULT_REFERENCE_FIELD,
):
    url = build_url(base_url, service_path)

    # Keep it simple. This tests whether SAP can find the invoice by Reference.
    params = {
        "$format": "json",
        "$filter": f"{reference_field} eq '{reference_value}'",
    }

    print("Calling SAP:")
    print(f"  URL: {url}")
    print(f"  Filter: {params['$filter']}")
    print()

    response = requests.get(
        url,
        params=params,
        auth=(user, password),
        headers={"Accept": "application/json"},
        timeout=30,
    )

    print(f"HTTP status: {response.status_code}")

    if response.status_code >= 400:
        print()
        print("SAP returned an error:")
        print(response.text[:3000])
        response.raise_for_status()

    data = response.json()
    return extract_odata_results(data)


def pick_invoice_fields(record: dict) -> dict:
    """
    SAP field names can vary by version/configuration.
    This prints common useful fields if they exist.
    """
    wanted_fields = [
        "SupplierInvoice",
        "FiscalYear",
        "CompanyCode",
        "Supplier",
        "SupplierName",
        "ReferenceDocument",
        "DocumentReferenceID",
        "SupplierInvoiceIDByInvcgParty",
        "InvoiceGrossAmount",
        "SupplierInvoiceGrossAmount",
        "DocumentCurrency",
        "PostingDate",
        "DocumentDate",
        "DueCalculationBaseDate",
        "PaymentTerms",
        "SupplierInvoiceStatus",
        "AccountingDocument",
    ]

    output = {}
    for field in wanted_fields:
        if field in record:
            output[field] = record.get(field)

    # Also show the first few extra fields so you can learn your API field names.
    extra_count = 0
    for key, value in record.items():
        if key not in output and not str(key).startswith("__"):
            output[key] = value
            extra_count += 1
        if extra_count >= 10:
            break

    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", required=True, help="Vendor invoice number stored in SAP Reference field")
    parser.add_argument("--service-path", default=DEFAULT_SERVICE_PATH, help="SAP OData entity path")
    parser.add_argument("--reference-field", default=DEFAULT_REFERENCE_FIELD, help="OData field name for SAP Reference")
    parser.add_argument("--out", default="", help="Optional Excel output path")
    args = parser.parse_args()

    base_url = get_env("SAP_BASE_URL")
    user = get_env("SAP_USER")
    password = get_env("SAP_PASSWORD")

    if not base_url or not user or not password:
        print()
        print("Example setup in Windows CMD:")
        print("  set SAP_BASE_URL=https://your-sap-host")
        print("  set SAP_USER=your_user")
        print("  set SAP_PASSWORD=your_password")
        sys.exit(1)

    results = fetch_supplier_invoice_by_reference(
        base_url=base_url,
        user=user,
        password=password,
        reference_value=args.reference,
        service_path=args.service_path,
        reference_field=args.reference_field,
    )

    print()
    print(f"Records found: {len(results)}")

    if not results:
        print()
        print("No invoice found.")
        print("Try another reference field, for example:")
        print(f"  py {Path(__file__).name} --reference {args.reference} --reference-field Reference")
        print(f"  py {Path(__file__).name} --reference {args.reference} --reference-field DocumentReferenceID")
        print(f"  py {Path(__file__).name} --reference {args.reference} --reference-field SupplierInvoiceIDByInvcgParty")
        return

    cleaned = [pick_invoice_fields(r) for r in results]

    print()
    print("First matching record:")
    for key, value in cleaned[0].items():
        print(f"  {key}: {value}")

    if args.out:
        df = pd.DataFrame(cleaned)
        df.to_excel(args.out, index=False)
        print()
        print(f"Saved Excel: {args.out}")


if __name__ == "__main__":
    main()
