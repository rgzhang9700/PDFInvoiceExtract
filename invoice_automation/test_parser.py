from pathlib import Path
import pdfplumber
from app.pdf_text import extract_pdf_text
from app.parsers.fleetpride_parser import FleetPrideParser
from app.parsers.valvoline_parser import ValvolineParser
#from app.parsers.GenericAPParser import GenericAPParser
#pdf_file = r"C:\PYTHON\invoice_automation_full_project_v4\invoice_automation\clients\sample_client\processed\FLEETPRIDE\FLEETPRIDE INV # 134869923.pdf"
#pdf_file = r"C:\PYTHON\PDFInvoiceExtract\invoice_automation\clients\sample_client\downloads\OILVANDOR\MY FLEET CENTER INV # 99923980.pdf"
#pdf_file = r"C:\PYTHON\PDFInvoiceExtract\invoice_automation\clients\northsky_comm\downloads\OILVENDOR\MY FLEET CENTER INV # 99923980.pdf"
#pdf_file = r"C:\PYTHON\PDFInvoiceExtract\invoice_automation\clients\northsky_comm\downloads\OILVENDOR\VALVOLINE INV # 167142.pdf"
pdf_file = r"C:\PYTHON\PDFInvoiceExtract\invoice_automation\clients\northsky_comm\downloads\THE CHARLES MACHINE INV # 93968775.PDF"
pdf_file = r"C:\PYTHON\PDFInvoiceExtract\invoice_automation\clients\northsky_comm\downloads\FLEETPRIDE INV # 134882087.PDF"
pdf_file = r"C:\PYTHON\PDFInvoiceExtract\invoice_automation\clients\northsky_comm\downloads\DITCH WITCH WEST INV # 1005638 VENDOR ID # V01988.pdf"
#pdf_file = r"C:\PYTHON\PDFInvoiceExtract\invoice_automation\clients\northsky_comm\downloads\F005632-154281-001 - ENTERED.pdf"
pdf_file = r"C:\PYTHON\PDFInvoiceExtract\invoice_automation\clients\northsky_comm\downloads\67000553452.pdf"
def main():
    print(pdf_file)
    text, pdf_type = extract_pdf_text(pdf_file)

    parser = ValvolineParser()
    #parser = JiffyLubeParser()
    #parser = FleetPrideParser()

    print(text)
    invoice = parser.parse(text)

    print("\n========== PARSED RESULT ==========\n")

    for key, value in invoice.items():
        print(f"{key}: {value}")

    print("\n========== VALIDATION ==========\n")
 
    print(f"[OK] Amount Found: {invoice['Company_code']}")
    
    if invoice.get("amount"):
        print(f"[OK] Amount Found: {invoice['amount']}")
    else:
        print("[X] Amount NOT Found")

    if invoice.get("invoice_number"):
        print(f"[OK] Invoice Number Found: {invoice['invoice_number']}")
    else:
        print("[X] Invoice Number NOT Found")

    if invoice.get("invoice_date"):
        print(f"[OK] Invoice Date Found: {invoice['invoice_date']}")
    else:
        print("[X] Invoice Date NOT Found")


if __name__ == "__main__":
    main()

