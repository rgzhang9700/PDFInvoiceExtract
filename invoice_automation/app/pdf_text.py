import pdfplumber
import easyocr
import numpy as np
from pdf2image import convert_from_path


OCR_READER = None
POPPLER_PATH = r"C:\Poppler\poppler-26.02.0\Library\bin"

def get_ocr_reader():
    global OCR_READER
    if OCR_READER is None:
        print("Loading EasyOCR model...")
        OCR_READER = easyocr.Reader(["en"], gpu=False)
    return OCR_READER


def extract_pdf_text(pdf_file, min_text_length=30):
    text = extract_real_pdf_text(pdf_file)
    if len(text.strip()) >= min_text_length:
        return text, "real_pdf"

    text = extract_image_pdf_text(pdf_file)
    return text, "scanned_pdf"


def extract_real_pdf_text(pdf_file):
    text_parts = []
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    text_parts.append(page_text)
    except Exception as e:
        print(f"pdfplumber failed for {pdf_file}: {e}")

    return "\n".join(text_parts).strip()


def extract_image_pdf_text(pdf_file):
    reader = get_ocr_reader()
    images = convert_from_path(str(pdf_file),dpi=300,poppler_path=POPPLER_PATH)

    text_parts = []
    for page_num, image in enumerate(images, start=1):
        print(f"EasyOCR reading page {page_num}...")
        img_array = np.array(image)
        results = reader.readtext(img_array, detail=0)
        text_parts.append(f"--- Page {page_num} ---")
        text_parts.append("\n".join(results))

    return "\n".join(text_parts).strip()