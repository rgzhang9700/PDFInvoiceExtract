#!/usr/bin/env python3
"""
TIPCO statement printer + SAP S/4HANA Supplier Invoice reconciliation.

This version assumes the TIPCO invoice number is stored in SAP field:

    Reference

For SAP S/4HANA OData, the screen field "Reference" is commonly exposed as one of:
    ReferenceDocument
    DocumentReferenceID
    SupplierInvoiceIDByInvcgParty

Default here:
    SAP_REFERENCE_FIELD = "ReferenceDocument"

If your SAP API metadata shows the property is exactly "Reference", change:
    SAP_REFERENCE_FIELD = "ReferenceDocument"
to:
    SAP_REFERENCE_FIELD = "Reference"

Prints:
    invoice_no
    invoice_amount
    supplier_id
    supplier_name

Print only:
    py tipco_print_and_sap_reference.py --statement "TIPCO(1).pdf" --supplier-id YOUR_VENDOR_ID

Direct SAP OData:
    set SAP_BASE_URL=https://your-sap-host
    set SAP_USER=your_user
    set SAP_PASSWORD=your_password

    py tipco_print_and_sap_reference.py ^
      --statement "TIPCO(1).pdf" ^
      --supplier-id YOUR_VENDOR_ID ^
      --sap-odata-url "/sap/opu/odata/sap/API_SUPPLIERINVOICE_PROCESS_SRV/A_SupplierInvoice" ^
      --out tipco_sap_reconciliation.xlsx
"""

import argparse
import os
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, Optional

import pandas as pd


SUPPLIER_NAME_DEFAULT = "TIPCO Technologies"

# SAP GUI field: Reference
# OData property commonly used for that field:
SAP_REFERENCE_FIELD = "ReferenceDocument"


def money_to_decimal(value) -> Decimal:
    if pd.isna(value):
        return Decimal("0.00")

    s = str(value).strip()
    s = s.replace("$", "").replace(",", "").replace(" ", "")

    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]

    try:
        return Decimal(s).quantize(Decimal("0.01"))
    except InvalidOperation:
        return Decimal("0.00")


def normalize_invoice_no(value) -> str:
    if pd.isna(value):
        return ""

    s = str(value).strip()

    if re.fullmatch(r"\d+\.0", s):
        s = s[:-2]

    return re.sub(r"\D", "", s)


def extract_text_from_pdf(pdf_path: Path) -> str:
    try:
        import pdfplumber
    except ImportError:
        raise SystemExit("Missing package: pdfplumber\nInstall it with:\n  pip install pdfplumber")

    text_parts = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            text_parts.append(page.extract_text() or "")

    return "\n".join(text_parts)


def extract_tipco_lines(statement_pdf: Path, supplier_id: str = "") -> pd.DataFrame:
    text = extract_text_from_pdf(statement_pdf)
    rows = []

    line_re = re.compile(
        r"(?m)^\s*"
        r"(?P<invoice_no>\d{8,12})\s+"
        r"(?P<invoice_date>\d{2}/\d{2}/\d{4})\s+"
        r"(?P<due_date>\d{2}/\d{2}/\d{4})\s+"
        r"(?P<middle>.*?)\s+"
        r"(?P<amount>-?\d{1,3}(?:,\d{3})*\.\d{2}|-?\d+\.\d{2})\s+"
        r"(?P<repeat_invoice_no>\d{8,12})\s*$"
    )

    for m in line_re.finditer(text):
        invoice_no = normalize_invoice_no(m.group("invoice_no"))
        repeat_invoice_no = normalize_invoice_no(m.group("repeat_invoice_no"))

        if invoice_no != repeat_invoice_no:
            continue

        rows.append(
            {
                "invoice_no": invoice_no,
                "invoice_amount": money_to_decimal(m.group("amount")),
                "supplier_id": supplier_id,
                "supplier_name": SUPPLIER_NAME_DEFAULT,
                "invoice_date": m.group("invoice_date"),
                "due_date": m.group("due_date"),
            }
        )

    if not rows:
        raise SystemExit("No TIPCO invoice lines found in the statement PDF.")

    return pd.DataFrame(rows).drop_duplicates(subset=["invoice_no", "invoice_amount"])


def print_invoice_table(df: pd.DataFrame):
    print("\nTIPCO statement invoice lines")
    print("=" * 90)

    display_df = df[["invoice_no", "invoice_amount", "supplier_id", "supplier_name"]].copy()
    display_df["invoice_amount"] = display_df["invoice_amount"].apply(lambda x: f"{x:,.2f}")

    print(display_df.to_string(index=False))

    total = sum(df["invoice_amount"], Decimal("0.00"))
    print("-" * 90)
    print(f"Invoice count: {len(df)}")
    print(f"Statement total: {total:,.2f}")
    print("=" * 90)


def sap_json_results(data: dict):
    if "d" in data and isinstance(data["d"], dict):
        if "results" in data["d"]:
            return data["d"]["results"]
        return [data["d"]]

    if "value" in data:
        return data["value"]

    return []


def fetch_sap_invoice_by_reference(invoice_no: str, sap_odata_url: str) -> Optional[Dict]:
    """
    Fetch SAP invoice using the SAP Reference field.

    Filter example:
        ReferenceDocument eq '351331095'
    """
    try:
        import requests
    except ImportError:
        raise SystemExit("Missing package: requests\nInstall it with:\n  pip install requests")

    base_url = os.environ.get("SAP_BASE_URL", "").rstrip("/")
    sap_user = os.environ.get("SAP_USER", "")
    sap_password = os.environ.get("SAP_PASSWORD", "")

    if not base_url or not sap_user or not sap_password:
        raise SystemExit(
            "Missing SAP connection settings.\n"
            "Set these environment variables first:\n"
            "  SAP_BASE_URL\n"
            "  SAP_USER\n"
            "  SAP_PASSWORD"
        )

    url = base_url + sap_odata_url

    params = {
        "$format": "json",
        "$filter": f"{SAP_REFERENCE_FIELD} eq '{invoice_no}'",
    }

    response = requests.get(url, params=params, auth=(sap_user, sap_password), timeout=30)
    response.raise_for_status()

    results = sap_json_results(response.json())

    if not results:
        return None

    rec = results[0]

    sap_amount_value = (
        rec.get("InvoiceGrossAmount")
        or rec.get("SupplierInvoiceGrossAmount")
        or rec.get("AmountInTransactionCurrency")
        or rec.get("GrossAmount")
        or rec.get("Amount")
        or 0
    )

    return {
        "sap_reference": rec.get(SAP_REFERENCE_FIELD, ""),
        "sap_amount": money_to_decimal(sap_amount_value),
        "sap_supplier_id": str(rec.get("Supplier") or rec.get("Vendor") or ""),
        "sap_supplier_name": str(rec.get("SupplierName") or rec.get("VendorName") or ""),
        "sap_company_code": str(rec.get("CompanyCode") or ""),
        "sap_fiscal_year": str(rec.get("FiscalYear") or ""),
        "sap_supplier_invoice": str(rec.get("SupplierInvoice") or ""),
    }


def reconcile_with_sap_odata(statement_df: pd.DataFrame, sap_odata_url: str) -> pd.DataFrame:
    rows = []

    for _, stmt in statement_df.iterrows():
        invoice_no = stmt["invoice_no"]
        statement_amount = stmt["invoice_amount"]

        sap_rec = fetch_sap_invoice_by_reference(invoice_no, sap_odata_url)

        if not sap_rec:
            rows.append(
                {
                    "status": "MISSING_IN_SAP",
                    "invoice_no": invoice_no,
                    "statement_amount": float(statement_amount),
                    "sap_reference": "",
                    "sap_amount": "",
                    "difference_statement_minus_sap": float(statement_amount),
                    "supplier_id": stmt["supplier_id"],
                    "supplier_name": stmt["supplier_name"],
                    "sap_supplier_id": "",
                    "sap_supplier_name": "",
                    "sap_supplier_invoice": "",
                    "sap_company_code": "",
                    "sap_fiscal_year": "",
                }
            )
            continue

        sap_amount = sap_rec["sap_amount"]
        difference = (statement_amount - sap_amount).quantize(Decimal("0.01"))
        status = "MATCH" if difference == Decimal("0.00") else "AMOUNT_MISMATCH"

        rows.append(
            {
                "status": status,
                "invoice_no": invoice_no,
                "statement_amount": float(statement_amount),
                "sap_reference": sap_rec.get("sap_reference", ""),
                "sap_amount": float(sap_amount),
                "difference_statement_minus_sap": float(difference),
                "supplier_id": stmt["supplier_id"],
                "supplier_name": stmt["supplier_name"],
                "sap_supplier_id": sap_rec.get("sap_supplier_id", ""),
                "sap_supplier_name": sap_rec.get("sap_supplier_name", ""),
                "sap_supplier_invoice": sap_rec.get("sap_supplier_invoice", ""),
                "sap_company_code": sap_rec.get("sap_company_code", ""),
                "sap_fiscal_year": sap_rec.get("sap_fiscal_year", ""),
            }
        )

    return pd.DataFrame(rows)


def write_excel(df: pd.DataFrame, out_path: Path):
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Reconciliation")

        summary = pd.DataFrame(
            [
                {"metric": "invoice_count", "value": len(df)},
                {"metric": "statement_total", "value": df["statement_amount"].sum()},
                {
                    "metric": "sap_total",
                    "value": pd.to_numeric(df.get("sap_amount", pd.Series(dtype=float)), errors="coerce").fillna(0).sum(),
                },
                {
                    "metric": "difference_total",
                    "value": pd.to_numeric(df.get("difference_statement_minus_sap", pd.Series(dtype=float)), errors="coerce").fillna(0).sum(),
                },
                {"metric": "match_count", "value": int((df.get("status", "") == "MATCH").sum()) if "status" in df else ""},
                {"metric": "missing_in_sap_count", "value": int((df.get("status", "") == "MISSING_IN_SAP").sum()) if "status" in df else ""},
                {"metric": "amount_mismatch_count", "value": int((df.get("status", "") == "AMOUNT_MISMATCH").sum()) if "status" in df else ""},
            ]
        )
        summary.to_excel(writer, index=False, sheet_name="Summary")

        wb = writer.book
        for ws in wb.worksheets:
            ws.freeze_panes = "A2"
            for col in ws.columns:
                max_len = max(len(str(cell.value or "")) for cell in col)
                ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 45)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--statement", required=True, help="TIPCO statement PDF")
    parser.add_argument("--supplier-id", default="", help="SAP supplier/vendor ID")
    parser.add_argument("--sap-odata-url", default="", help="SAP S/4HANA OData endpoint path")
    parser.add_argument("--out", default="", help="Optional output Excel file")
    args = parser.parse_args()

    statement_pdf = Path(args.statement)

    if not statement_pdf.exists():
        raise SystemExit(f"Statement PDF not found: {statement_pdf}")

    statement_df = extract_tipco_lines(statement_pdf, supplier_id=args.supplier_id)

    # Always print invoice #, amount, supplier ID, supplier name.
    print_invoice_table(statement_df)

    result_df = statement_df.copy()
    result_df["invoice_amount"] = result_df["invoice_amount"].astype(float)

    if args.sap_odata_url:
        result_df = reconcile_with_sap_odata(statement_df, args.sap_odata_url)
        print("\nSAP S/4HANA reconciliation by Reference")
        print(result_df.to_string(index=False))

    if args.out:
        write_excel(result_df, Path(args.out))
        print(f"\nExcel output written to: {args.out}")


if __name__ == "__main__":
    main()
