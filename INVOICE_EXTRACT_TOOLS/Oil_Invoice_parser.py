import re
import pdfplumber
import easyocr
from pdf2image import convert_from_path
import numpy as np
#import fitz  # pip install PyMuPDF

pdf_file = r"C:\PYTHONCODE\Python_Script\VALVOLINE INV # 169564.pdf"


def Get_Valvoline_invoice(pdf_file):
    """
    Extracts Invoice Number, Date, and Total from a Valvoline invoice PDF.
    Returns a dictionary with the extracted fields.
    """
    # Initialize variables
    invoice_no = "Not Valvoline"
    date_val = "Not Valvoline"
    total_val = "Not Valvoline"
                
    with pdfplumber.open(pdf_file) as pdf:
        # Extract text from the first page
        full_text = pdf.pages[0].extract_text()
            
        if "VALVOLINE" in full_text.upper():        
            # Step 1: Parse the top header line
            header_match = re.search(r"Invoice\s+(\d+)\s+(\d{1,2}/\d{1,2}/\d{4})", full_text, re.IGNORECASE)
            if header_match:
                invoice_no = header_match.group(1)
                date_val = header_match.group(2)
                        
            # Step 2: Parse the absolute Total amount line
            total_match = re.search(r"Total\s+([\d\.]+)", full_text, re.IGNORECASE)
            if total_match:
                total_val = total_match.group(1)
                    
    return invoice_no, date_val, total_val
    
#Image processing not working yet
def Get_Valvoline_invoice_Image(pdf_file):
    # Initialize variables
    invoice_no = "Not Valvoline"
    date_val = "Not Valvoline"
    total_val = "Not Valvoline"
    
    images = convert_from_path(pdf_file, poppler_path=r'C:\Poppler\poppler-26.02.0\Library\bin')
    # Initialize the EasyOCR reader (loads the model into memory)
    # You can add more languages to the list, e.g., ['en', 'es']
    print("Loading EasyOCR model...")
    reader = easyocr.Reader(['en']) 
    
    full_text = ""
    
    for page_num, img in enumerate(images, start=1):
        print(f"Reading page {page_num}...")
        
        # EasyOCR expects a numpy array, so we convert the PIL image
        img_array = np.array(img)
        
        # detail=0 returns just the text. 
        # detail=1 (default) returns bounding box coordinates and confidence scores too.
        results = reader.readtext(img_array, detail=0)
       
        full_text += f"\n--- Page {page_num} ---\n"
        full_text += "\n".join(results)
        
        #print(full_text)
        
        if "VALVOLINE" in full_text.upper():      
            # Step 1: Parse the top header line
            header_match = re.search(r"Invoice\s+(\d+)\s+(\d{1,2}/\d{1,2}/\d{2})", full_text)
            if header_match:
                invoice_no = header_match.group(1)
                date_val = header_match.group(2)
                            
            # Step 2: Parse the absolute Total amount line
            total_match = re.search(r"Total\s+([\d\.]+)", full_text, re.IGNORECASE)
            if total_match:
                total_val = total_match.group(1)
                    
    return invoice_no, date_val, total_val
    

#def is_scanned(file_path):
#   doc = fitz.open(file_path)
 #   
  #  for page in doc:
   #     # If we can extract any text, it is not a scanned image
    #    if page.get_text().strip():
     #       return False 
            
    # If no text was found on any page, it is a scan
    #return True