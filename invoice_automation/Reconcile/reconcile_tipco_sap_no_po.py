#!/usr/bin/env python3
"""
Reconcile a TIPCO statement PDF to a SAP export.

NO PO check.
NO duplicate check because SAP already controls/checks duplicates.

Compares only:
  1) TIPCO invoice number  -> SAP invoice/reference number
  2) TIPCO amount          -> SAP amount

Output:
  Excel file with Summary and Reconciliation tabs.

Example:
  py reconcile_tipco_sap_no_duplicate.py --statement "TIPCO(1).pdf" --sap-export sap_open_items.xlsx --out tipco_sap_reconciliation.xlsx
"""

import argparse
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd


def money_to_decimal(value) -> Decimal:
    """Convert strings like '1,234.56', '-78.78', '$1,234.56' to Decimal."""
    if pd.isna(value):
        return Decimal("0.00")

    s = str(value).strip()
    s = s.replace("$", "").replace(",", "").replace(" ", "")

    # Handle parentheses negative format: (123.45)
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]

    try:
        return Decimal(s).quantize(Decimal("0.01"))
    except InvalidOperation:
        return Decimal("0.00")


def normalize_invoice_no(value) -> str:
    """Normalize invoice number for matching."""
    if pd.isna(value):
        return ""

    s = str(value).strip()

    # Excel may read invoice number as 351331095.0
    if re.fullmatch(r"\d+\.0", s):
        s = s[:-2]

    # Keep only digits for TIPCO invoice numbers
    digits = re.sub(r"\D", "", s)
    return digits


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text from PDF using pdfplumber."""
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
            page_text = page.extract_text() or ""
            text_parts.append(page_text)

    return "\n".join(text_parts)


def extract_tipco_statement_lines(statement_pdf: Path) -> pd.DataFrame:
    """
    Extract invoice lines from TIPCO statement.

    Expected line shape:
      351331095 04/01/2026 05/01/2026 OOEQUIP/ Tom 64.95 351331095

    We do NOT use PO number for reconciliation.
    """
    text = extract_text_from_pdf(statement_pdf)

    rows = []

    # Invoice number, invoice date, due date, any text/PO column, amount, repeated invoice no
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

        # Safety check: the repeated invoice number on the right side should match.
        if invoice_no != repeat_invoice_no:
            continue

        rows.append(
            {
                "statement_invoice_no": invoice_no,
                "statement_invoice_date": m.group("invoice_date"),
                "statement_due_date": m.group("due_date"),
                "statement_amount": money_to_decimal(m.group("amount")),
                "statement_middle_text": m.group("middle").strip(),
            }
        )

    if not rows:
        raise SystemExit(
            "No TIPCO invoice lines found in statement PDF. "
            "Check whether the PDF text extraction is readable."
        )

    df = pd.DataFrame(rows)

    # Keep one row per statement invoice number.
    # If the statement itself repeats a line, this prevents double counting.
    df = df.drop_duplicates(subset=["statement_invoice_no", "statement_amount"])

    return df


def find_column(df: pd.DataFrame, candidates) -> str:
    """Find a column by common possible names."""
    normalized = {str(c).strip().lower(): c for c in df.columns}

    for name in candidates:
        key = name.strip().lower()
        if key in normalized:
            return normalized[key]

    # Looser matching
    for c in df.columns:
        c_norm = str(c).strip().lower().replace("_", " ")
        for name in candidates:
            name_norm = name.strip().lower().replace("_", " ")
            if c_norm == name_norm:
                return c

    raise SystemExit(
        "Could not find required column.\n"
        f"Expected one of: {candidates}\n"
        f"Available columns: {list(df.columns)}"
    )


def read_sap_export(sap_path: Path) -> pd.DataFrame:
    """Read SAP export from xlsx/xls/csv."""
    suffix = sap_path.suffix.lower()

    if suffix in [".xlsx", ".xlsm", ".xls"]:
        df = pd.read_excel(sap_path)
    elif suffix == ".csv":
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
            "Reference No",
            "Document Reference",
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

    out = df.copy()
    out["sap_invoice_no_norm"] = out[invoice_col].apply(normalize_invoice_no)
    out["sap_amount_decimal"] = out[amount_col].apply(money_to_decimal)

    # Keep original useful columns too.
    out["_sap_invoice_source_column"] = invoice_col
    out["_sap_amount_source_column"] = amount_col

    return out


def reconcile(statement_df: pd.DataFrame, sap_df: pd.DataFrame) -> pd.DataFrame:
    """
    Match TIPCO statement to SAP by invoice number.
    No duplicate checking. If SAP has multiple rows for the same invoice,
    this script compares against the first matching row only because SAP duplicate
    control is handled separately.
    """
    # First SAP row per invoice number for matching.
    sap_first = sap_df.drop_duplicates(subset=["sap_invoice_no_norm"], keep="first")

    merged = statement_df.merge(
        sap_first,
        how="left",
        left_on="statement_invoice_no",
        right_on="sap_invoice_no_norm",
        suffixes=("", "_sap"),
    )

    results = []
    for _, row in merged.iterrows():
        statement_amount = row["statement_amount"]
        sap_amount = row.get("sap_amount_decimal", Decimal("0.00"))

        if pd.isna(row.get("sap_invoice_no_norm")) or str(row.get("sap_invoice_no_norm", "")).strip() == "":
            status = "MISSING_IN_SAP"
            difference = statement_amount
        else:
            difference = (statement_amount - sap_amount).quantize(Decimal("0.01"))
            if difference == Decimal("0.00"):
                status = "MATCH"
            else:
                status = "AMOUNT_MISMATCH"

        results.append(
            {
                "status": status,
                "invoice_no": row["statement_invoice_no"],
                "statement_invoice_date": row["statement_invoice_date"],
                "statement_due_date": row["statement_due_date"],
                "statement_amount": float(statement_amount),
                "sap_amount": float(sap_amount) if status != "MISSING_IN_SAP" else "",
                "difference_statement_minus_sap": float(difference),
                "statement_middle_text": row.get("statement_middle_text", ""),
            }
        )

    return pd.DataFrame(results)


def write_report(recon_df: pd.DataFrame, out_path: Path):
    summary = pd.DataFrame(
        [
            {"metric": "statement_invoice_count", "value": len(recon_df)},
            {"metric": "statement_total", "value": recon_df["statement_amount"].sum()},
            {
                "metric": "sap_matched_total",
                "value": pd.to_numeric(recon_df["sap_amount"], errors="coerce").fillna(0).sum(),
            },
            {
                "metric": "difference_total",
                "value": recon_df["difference_statement_minus_sap"].sum(),
            },
            {"metric": "match_count", "value": int((recon_df["status"] == "MATCH").sum())},
            {
                "metric": "missing_in_sap_count",
                "value": int((recon_df["status"] == "MISSING_IN_SAP").sum()),
            },
            {
                "metric": "amount_mismatch_count",
                "value": int((recon_df["status"] == "AMOUNT_MISMATCH").sum()),
            },
        ]
    )

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        summary.to_excel(writer, index=False, sheet_name="Summary")
        recon_df.to_excel(writer, index=False, sheet_name="Reconciliation")

        wb = writer.book

        for ws in wb.worksheets:
            ws.freeze_panes = "A2"
            for col in ws.columns:
                max_len = 0
                col_letter = col[0].column_letter
                for cell in col:
                    val = "" if cell.value is None else str(cell.value)
                    max_len = max(max_len, len(val))
                ws.column_dimensions[col_letter].width = min(max_len + 2, 45)

        # Format amount columns
        if "Reconciliation" in wb.sheetnames:
            ws = wb["Reconciliation"]
            headers = [cell.value for cell in ws[1]]
            for amount_header in [
                "statement_amount",
                "sap_amount",
                "difference_statement_minus_sap",
            ]:
                if amount_header in headers:
                    col_idx = headers.index(amount_header) + 1
                    for row in range(2, ws.max_row + 1):
                        ws.cell(row=row, column=col_idx).number_format = '#,##0.00;[Red]-#,##0.00'

        if "Summary" in wb.sheetnames:
            ws = wb["Summary"]
            for row in range(2, ws.max_row + 1):
                ws.cell(row=row, column=2).number_format = '#,##0.00;[Red]-#,##0.00'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--statement", required=True, help="TIPCO statement PDF path")
    parser.add_argument("--sap-export", required=True, help="SAP export .xlsx/.csv path")
    parser.add_argument("--out", default="tipco_sap_reconciliation.xlsx", help="Output Excel report")
    args = parser.parse_args()

    statement_pdf = Path(args.statement)
    sap_path = Path(args.sap_export)
    out_path = Path(args.out)

    if not statement_pdf.exists():
        raise SystemExit(f"Statement PDF not found: {statement_pdf}")

    if not sap_path.exists():
        raise SystemExit(f"SAP export not found: {sap_path}")

    statement_df = extract_tipco_statement_lines(statement_pdf)
    sap_df = read_sap_export(sap_path)
    recon_df = reconcile(statement_df, sap_df)
    write_report(recon_df, out_path)

    print(f"Done: {out_path}")
    print("No PO check. No duplicate check.")
    print(recon_df["status"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
