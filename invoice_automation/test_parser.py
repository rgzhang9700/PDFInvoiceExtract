from pathlib import Path
import pdfplumber
from app.pdf_text import extract_pdf_text

from app.parsers.fleetpride_parser import FleetPrideParser
pdf_file = r"C:\PYTHON\invoice_automation_full_project_v4\invoice_automation\clients\sample_client\processed\FLEETPRIDE\FLEETPRIDE INV # 134869923.pdf"

def main():

    text, pdf_type = extract_pdf_text(pdf_file)
    print("PDF Type:", pdf_type)
    parser = FleetPrideParser()

    invoice = parser.parse(text)

    print("\n========== PARSED RESULT ==========\n")

    for key, value in invoice.items():
        print(f"{key}: {value}")

    print("\n========== VALIDATION ==========\n")

    if invoice.get("amount"):
        print(f"✓ Amount Found: {invoice['amount']}")
    else:
        print("✗ Amount NOT Found")

    if invoice.get("invoice_number"):
        print(f"✓ Invoice Number Found: {invoice['invoice_number']}")
    else:
        print("✗ Invoice Number NOT Found")

    if invoice.get("invoice_date"):
        print(f"✓ Invoice Date Found: {invoice['invoice_date']}")
    else:
        print("✗ Invoice Date NOT Found")


if __name__ == "__main__":
    main()

