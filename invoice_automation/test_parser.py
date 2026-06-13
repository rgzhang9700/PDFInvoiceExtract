from pathlib import Path
import pdfplumber
from app.pdf_text import extract_pdf_text
from app.parsers.fleetpride_parser import FleetPrideParser
from app.parsers.valvoline_parser import ValvolineParser
#from app.parsers.GenericAPParser import GenericAPParser
pdf_file = r"C:\PYTHON\PDFInvoiceExtract\invoice_automation\clients\northsky_comm\downloads\RDO INV # P5969477.PDF"
#pdf_file = r"C:\PYTHON\PDFInvoiceExtract\invoice_automation\clients\sample_client\downloads\OILVANDOR\MY FLEET CENTER INV # 99923980.pdf"
#pass pdf_file = r"C:\PYTHON\PDFInvoiceExtract\invoice_automation\clients\northsky_comm\downloads\DITCH WITCH INV # 1051257.pdf"
#pdf_file = r"C:\PYTHON\PDFInvoiceExtract\invoice_automation\clients\northsky_comm\downloads\Invoice_882430_.pdf"
#pdf_file = r"C:\PYTHON\PDFInvoiceExtract\invoice_automation\clients\northsky_comm\downloads\DELTA TRUCK CENTER INV R008177111 01.pdf"
#pdf_file = r"C:\PYTHON\PDFInvoiceExtract\invoice_automation\clients\northsky_comm\downloads\PAPE KENWORTH INV # 16160709.pdf"
#pdf_file = r"C:\PYTHON\PDFInvoiceExtract\invoice_automation\clients\northsky_comm\downloads\RANDALL CREEK INV # 260302.pdf"
##FAIL
#pdf_file = r"C:\PYTHON\PDFInvoiceExtract\invoice_automation\clients\northsky_comm\downloads\CONTINENTAL INV # 5055242618 $ 1924.22.pdf"
#pdf_file = r"C:\PYTHON\PDFInvoiceExtract\invoice_automation\clients\northsky_comm\downloads\67000553452.pdf"
pdf_file = r"C:\PYTHONCODE\PDFInvoiceExtract\invoice_automation\clients\northsky_comm\downloads\CONTINENTAL TIRES INV # 5047289398 $ 721.59 (1).pdf"
def main():
    print(pdf_file)
    text, pdf_type = extract_pdf_text(pdf_file)

    #parser = ValvolineParser()
    parser = FleetPrideParser()

    print(text)
    invoice = parser.parse(text)

    print("\n========== PARSED RESULT ==========\n")

    for key, value in invoice.items():
        print(f"{key}: {value}")

    print("\n========== VALIDATION ==========\n")
 
    print(f"[OK] Amount Found: {invoice['vendor_id']}")
    
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

