#!/usr/bin/env python3
"""
TIPCO statement printer + optional SAP direct reconciliation.

Prints:
  invoice_no
  invoice_amount
  supplier_id
  supplier_name

For direct SAP fetch:
  This script includes a generic SAP OData example.
  Your SAP system must expose an invoice API / CDS view / custom OData service.
  If your SAP does not expose this exact endpoint, change SAP_ODATA_URL and field names.

Basic print only:
  py tipco_print_and_sap_reconcile.py --statement "TIPCO(1).pdf" --supplier-id VENDOR_ID_FROM_SAP

Print + reconcile from SAP export:
  py tipco_print_and_sap_reconcile.py --statement "TIPCO(1).pdf" --sap-export sap_open_items.xlsx --supplier-id VENDOR_ID_FROM_SAP

Print + try direct SAP OData:
  set SAP_BASE_URL=https://your-sap-host
  set SAP_USER=your_user
  set SAP_PASSWORD=your_password

  py tipco_print_and_sap_reconcile.py --statement "TIPCO(1).pdf" --sap-odata-url "/sap/opu/odata/sap/YOUR_SERVICE/InvoiceSet" --supplier-id VENDOR_ID_FROM_SAP
"""

import argparse
import os
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd


SUPPLIER_NAME_DEFAULT = "TIPCO Technologies"


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

    # Excel sometimes reads invoice as 351331095.0
    if re.fullmatch(r"\d+\.0", s):
        s = s[:-2]

    return re.sub(r"\D", "", s)


def extract_text_from_pdf(pdf_path: Path) -> str:
    try:
        import pdfplumber
    except ImportError:
        raise SystemExit(
            "Missing package: pdfplumber\n"
            "Install it with:\n"
            "  pip install pdfplumber"
        )

    text_parts = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            text_parts.append(page.extract_text() or "")

    return "\n".join(text_parts)


def extract_tipco_lines(statement_pdf: Path, supplier_id: str = "") -> pd.DataFrame:
    """
    Extract TIPCO statement invoice lines.

    PDF line example:
      351331095 04/01/2026 05/01/2026 OOEQUIP/ Tom 64.95 351331095
    """
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

    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset=["invoice_no", "invoice_amount"])
    return df


def print_invoice_table(df: pd.DataFrame):
    print("\nTIPCO statement invoice lines")
    print("=" * 80)

    display_df = df[["invoice_no", "invoice_amount", "supplier_id", "supplier_name"]].copy()
    display_df["invoice_amount"] = display_df["invoice_amount"].apply(lambda x: f"{x:,.2f}")

    print(display_df.to_string(index=False))

    total = sum(df["invoice_amount"], Decimal("0.00"))
    print("-" * 80)
    print(f"Invoice count: {len(df)}")
    print(f"Statement total: {total:,.2f}")
    print("=" * 80)


def find_column(df: pd.DataFrame, candidates: List[str]) -> str:
    normalized = {str(c).strip().lower(): c for c in df.columns}

    for name in candidates:
        if name.strip().lower() in normalized:
            return normalized[name.strip().lower()]

    raise SystemExit(
        "Could not find required SAP export column.\n"
        f"Expected one of: {candidates}\n"
        f"Available columns: {list(df.columns)}"
    )


def read_sap_export(sap_path: Path) -> pd.DataFrame:
    if sap_path.suffix.lower() in [".xlsx", ".xlsm", ".xls"]:
        df = pd.read_excel(sap_path)
    elif sap_path.suffix.lower() == ".csv":
        df = pd.read_csv(sap_path)
    else:
        raise SystemExit("SAP export must be .xlsx, .xls, .xlsm, or .csv")

    invoice_col = find_column(
        df,
        [
            "Invoice Number",
            "Invoice No",
            "Invoice",
            "Reference",
            "Reference Number",
            "Vendor Invoice Number",
            "Supplier Invoice",
            "Supplier Invoice Number",
        ],
    )

    amount_col = find_column(
        df,
        [
            "Amount",
            "Document Amount",
            "Amount in Document Currency",
            "Gross Amount",
            "Invoice Amount",
            "Balance",
            "Open Amount",
        ],
    )

    supplier_id_col = None
    supplier_name_col = None

    for c in ["Supplier", "Supplier ID", "Vendor", "Vendor ID", "Business Partner"]:
        if c in df.columns:
            supplier_id_col = c
            break

    for c in ["Supplier Name", "Vendor Name", "Name", "Business Partner Name"]:
        if c in df.columns:
            supplier_name_col = c
            break

    out = pd.DataFrame()
    out["sap_invoice_no"] = df[invoice_col].apply(normalize_invoice_no)
    out["sap_amount"] = df[amount_col].apply(money_to_decimal)
    out["sap_supplier_id"] = df[supplier_id_col].astype(str) if supplier_id_col else ""
    out["sap_supplier_name"] = df[supplier_name_col].astype(str) if supplier_name_col else ""

    return out


def reconcile_with_sap_export(statement_df: pd.DataFrame, sap_df: pd.DataFrame) -> pd.DataFrame:
    sap_first = sap_df.drop_duplicates(subset=["sap_invoice_no"], keep="first")

    merged = statement_df.merge(
        sap_first,
        how="left",
        left_on="invoice_no",
        right_on="sap_invoice_no",
    )

    rows = []
    for _, row in merged.iterrows():
        statement_amount = row["invoice_amount"]

        if pd.isna(row.get("sap_invoice_no")) or str(row.get("sap_invoice_no", "")).strip() == "":
            status = "MISSING_IN_SAP"
            sap_amount = ""
            difference = statement_amount
        else:
            sap_amount = row["sap_amount"]
            difference = (statement_amount - sap_amount).quantize(Decimal("0.01"))
            status = "MATCH" if difference == Decimal("0.00") else "AMOUNT_MISMATCH"

        rows.append(
            {
                "status": status,
                "invoice_no": row["invoice_no"],
                "statement_amount": float(statement_amount),
                "sap_amount": "" if sap_amount == "" else float(sap_amount),
                "difference_statement_minus_sap": float(difference),
                "supplier_id": row["supplier_id"],
                "supplier_name": row["supplier_name"],
                "sap_supplier_id": row.get("sap_supplier_id", ""),
                "sap_supplier_name": row.get("sap_supplier_name", ""),
            }
        )

    return pd.DataFrame(rows)


def fetch_sap_invoice_odata(invoice_no: str, sap_odata_url: str) -> Optional[Dict]:
    """
    Generic SAP OData invoice fetch.

    You must configure:
      SAP_BASE_URL
      SAP_USER
      SAP_PASSWORD

    Example:
      SAP_BASE_URL=https://mycompany.sap.com
      sap_odata_url=/sap/opu/odata/sap/YOUR_SERVICE/InvoiceSet

    This assumes your OData service supports $filter by invoice/reference number.
    Field names vary by SAP system, so update this function for your real service.
    """
    try:
        import requests
    except ImportError:
        raise SystemExit(
            "Missing package: requests\n"
            "Install it with:\n"
            "  pip install requests"
        )

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

    # IMPORTANT:
    # Change SupplierInvoice/ReferenceDocument field names to match your SAP OData service.
    params = {
        "$format": "json",
        "$filter": f"SupplierInvoice eq '{invoice_no}' or ReferenceDocument eq '{invoice_no}'",
    }

    response = requests.get(url, params=params, auth=(sap_user, sap_password), timeout=30)
    response.raise_for_status()

    data = response.json()

    # Common OData V2 shape: d.results
    results = data.get("d", {}).get("results", [])

    if not results:
        return None

    rec = results[0]

    # Update these field names to your SAP service.
    return {
        "sap_invoice_no": normalize_invoice_no(
            rec.get("SupplierInvoice")
            or rec.get("ReferenceDocument")
            or rec.get("InvoiceReference")
            or invoice_no
        ),
        "sap_amount": money_to_decimal(
            rec.get("InvoiceGrossAmount")
            or rec.get("AmountInTransactionCurrency")
            or rec.get("GrossAmount")
            or rec.get("Amount")
            or 0
        ),
        "sap_supplier_id": str(rec.get("Supplier") or rec.get("Vendor") or ""),
        "sap_supplier_name": str(rec.get("SupplierName") or rec.get("VendorName") or ""),
    }


def reconcile_with_sap_odata(statement_df: pd.DataFrame, sap_odata_url: str) -> pd.DataFrame:
    rows = []

    for _, stmt in statement_df.iterrows():
        invoice_no = stmt["invoice_no"]
        statement_amount = stmt["invoice_amount"]

        sap_rec = fetch_sap_invoice_odata(invoice_no, sap_odata_url)

        if not sap_rec:
            rows.append(
                {
                    "status": "MISSING_IN_SAP",
                    "invoice_no": invoice_no,
                    "statement_amount": float(statement_amount),
                    "sap_amount": "",
                    "difference_statement_minus_sap": float(statement_amount),
                    "supplier_id": stmt["supplier_id"],
                    "supplier_name": stmt["supplier_name"],
                    "sap_supplier_id": "",
                    "sap_supplier_name": "",
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
                "sap_amount": float(sap_amount),
                "difference_statement_minus_sap": float(difference),
                "supplier_id": stmt["supplier_id"],
                "supplier_name": stmt["supplier_name"],
                "sap_supplier_id": sap_rec.get("sap_supplier_id", ""),
                "sap_supplier_name": sap_rec.get("sap_supplier_name", ""),
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
                    "value": pd.to_numeric(df["sap_amount"], errors="coerce").fillna(0).sum(),
                },
                {
                    "metric": "difference_total",
                    "value": df["difference_statement_minus_sap"].sum(),
                },
                {"metric": "match_count", "value": int((df["status"] == "MATCH").sum())},
                {
                    "metric": "missing_in_sap_count",
                    "value": int((df["status"] == "MISSING_IN_SAP").sum()),
                },
                {
                    "metric": "amount_mismatch_count",
                    "value": int((df["status"] == "AMOUNT_MISMATCH").sum()),
                },
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
    parser.add_argument("--supplier-id", default="", help="Supplier/vendor ID from SAP, if known")
    parser.add_argument("--sap-export", default="", help="Optional SAP export .xlsx/.csv")
    parser.add_argument("--sap-odata-url", default="", help="Optional SAP OData endpoint path")
    parser.add_argument("--out", default="", help="Optional output Excel file")
    args = parser.parse_args()

    statement_pdf = Path(args.statement)

    if not statement_pdf.exists():
        raise SystemExit(f"Statement PDF not found: {statement_pdf}")

    statement_df = extract_tipco_lines(statement_pdf, supplier_id=args.supplier_id)

    # Always print invoice #, amount, supplier ID, supplier name.
    print_invoice_table(statement_df)

    result_df = None

    if args.sap_export:
        sap_df = read_sap_export(Path(args.sap_export))
        result_df = reconcile_with_sap_export(statement_df, sap_df)
        print("\nSAP export reconciliation")
        print(result_df.to_string(index=False))

    elif args.sap_odata_url:
        result_df = reconcile_with_sap_odata(statement_df, args.sap_odata_url)
        print("\nSAP direct OData reconciliation")
        print(result_df.to_string(index=False))

    if args.out:
        if result_df is None:
            # If only printing statement lines, save those.
            out_df = statement_df.copy()
            out_df["invoice_amount"] = out_df["invoice_amount"].astype(float)
        else:
            out_df = result_df

        write_excel(out_df, Path(args.out))
        print(f"\nExcel output written to: {args.out}")


if __name__ == "__main__":
    main()
