from pathlib import Path
import pdfplumber
from app.pdf_text import extract_pdf_text
from app.parsers.fleetpride_parser import FleetPrideParser
from app.parsers.jiffy_lube_parser import JiffyLubeParser
from app.parsers.les_schwab_parser import LesSchwabParser
#pdf_file = r"C:\PYTHON\invoice_automation_full_project_v4\invoice_automation\clients\sample_client\processed\FLEETPRIDE\FLEETPRIDE INV # 134869923.pdf"
#pdf_file = r"C:\PYTHON\PDFInvoiceExtract\invoice_automation\clients\sample_client\downloads\OILVANDOR\MY FLEET CENTER INV # 99923980.pdf"
pdf_file = r"C:\PYTHON\PDFInvoiceExtract\invoice_automation\clients\northsky_comm\downloads\LESHWEB\66800415007.pdf"

def main():
    print(pdf_file)
    text, pdf_type = extract_pdf_text(pdf_file)

    #parser = FleetPrideParser()
    #parser = JiffyLubeParser()
    parser = LesSchwabParser()

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

