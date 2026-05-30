import re
from PIL import Image
import pdfplumber
import Oil_Invoice_paser

pdf_file = r"C:\PYTHONCODE\Python_Script\VALVOLINE INV # 169564.pdf"

def Valvoline_invoice_details(pdf_file):
    """
    Extracts Invoice Number, Date, and Total from a Valvoline invoice PDF.
    Returns a dictionary with the extracted fields.
    """
    with pdfplumber.open(pdf_file) as pdf:
        # Extract text from the first page
        full_text = pdf.pages[0].extract_text()
    
    # Initialize variables
    invoice_no = None
    date_val = None
    total_val = None
    
    # Step 1: Parse the top header line
    header_match = re.search(r"Invoice\s+(\d+)\s+(\d{1,2}/\d{1,2}/\d{4})", full_text, re.IGNORECASE)
    if header_match:
        invoice_no = header_match.group(1)
        date_val = header_match.group(2)
        
    # Step 2: Parse the absolute Total amount line
    total_match = re.search(r"Total\s+([\d\.]+)", full_text, re.IGNORECASE)
    if total_match:
        total_val = total_match.group(1)
        
    # Return structured results
    return {
        "Invoice No": invoice_no,
        "Date": date_val,
        "Total": total_val
    }
    
