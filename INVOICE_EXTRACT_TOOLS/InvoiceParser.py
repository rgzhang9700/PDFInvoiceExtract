import re
import os
from PIL import Image
import pdfplumber
from Oil_Invoice_parser import Get_Valvoline_invoice
from Oil_Invoice_parser import Get_Valvoline_invoice_Image

file_direcory = r"C:\PYTHONCODE\Python_Script\Test"


for filename in os.listdir(file_direcory):
    file_path = os.path.join(file_direcory, filename)
    try:
        if "VALVOLINE" in filename.upper():
            inv, dt, tot = Get_Valvoline_invoice(file_path)
        else:
            inv, dt, tot = Get_Valvoline_invoice_Image(file_path)
            
        if inv == "Not Valvoline" or inv is None:
            print(f"Skipped (Not Valvoline): {filename}")
        else:
            print(f"Processed: {filename} -> Inv: {inv}, Date: {dt}, Total: {tot}")
                
    except Exception:
            # If the function throws an error or returns None, skip the file safely
            print(f"Skipped (Error parsing file): {filename}")

    