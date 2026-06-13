import re
from datetime import datetime
from .base import BaseInvoiceParser, lookup_tax_center_id, lookup_supplier_code,extract_vendor_invoice_from_filename
from datetime import datetime, timedelta

class ValvolineParser(BaseInvoiceParser):
    
    def parse(self, text, file_path):
        raw_text = text
        clean_text = self._clean_ocr_text(raw_text)
        text = self._clean_ocr_one_line(raw_text)
        
        if file_path:
            filename_info = extract_vendor_invoice_from_filename(file_path)
            vendor_name = filename_info.get("vendor_name")
            invoice_number = filename_info.get("invoice_number") 
        else:
            vendor_name = self._find_vendor_name(text) 
            invoice_number = self._find_invoice_number(text)

        service_address = self._find_service_center_address(text)
        ship_to_address = self._find_ship_to_address(text)
        vender_address = self._find_vendor_address(text)
        ship_to_postcode = self._find_postcode(ship_to_address)
        service_center_postcode =  self._find_postcode(service_address)
        vendor_postcode = self._find_postcode(vender_address)
        postcode_lookup = (ship_to_postcode or service_center_postcode or vendor_postcode)
       
        supplier_info = lookup_supplier_code(vendor_name)
        
        
        return {
            "vendor_name": vendor_name,
            "vendor_id": supplier_info["Supplier"],
            "vendor_address": vender_address,
            "vendor_postcode": self._find_postcode(vender_address),
            "ship_to_postcode": self._find_postcode(ship_to_address),
            "ship_to_address": ship_to_address,
            "service_center_address": service_address,
            "service_center_postcode": self._find_postcode(service_address),
            "invoice_number": invoice_number,
            "invoice_date": self._find_invoice_date(text),
            "amount": self._find_total(text),
            "po_number": self._find_po_number(text),
            "postcode_lookup" : postcode_lookup,
            "TAXCenterID": lookup_tax_center_id(postcode_lookup),
            "gl_account": supplier_info["GLAccount"],
            "ItemText": supplier_info["ItemText"],
            "Payee": supplier_info["Payee"],
        }   
        
    def _find_invoice_number(self, text):
        for pattern in [r"Invoice\s+(\d+)", 
                        r"Invoice\s*#?\s*(\d+)", 
                        r"Invoice #\s*:\s+(\d+)",
                        r"\bINVOICE\s+NUMBER\b[\s\S]{0,120}?(\d{6,})", 
                        r"INVOICE\s+NO\.?\s*\n\s*\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\s+(\d+)",
                        r"\bInvoice\s*:\s*(\d+)",
                        r"INVOICE\s+DATE\s+INVOICE\s+NO\.?\s*\n?\s*\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\s+(\d+)", #DITCH WITCH EUGENE
                        r"(?i)\binvoice\s*n[o0]\s*\.?\s*[:#-]?\s*(\d{4,})", #RANDALL
                        ]:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(1)
        return ""

    def _find_invoice_date_old(self, text):
        patterns = [
            r"Invoice\s+\d+\s+(\d{1,2}/\d{1,2}/\d{4})",
            r"Date\s*:\s*(\d{2}/\d{2}/\d{4})",
            r"\bInvoice\s+\d+\s+(\d{1,2}/\d{1,2}/\d{2,4})",
        ]
  
        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                value = m.group(1)
                for fmt in ("%m/%d/%Y", "%m/%d/%y"):
                    try:
                        return datetime.strptime(value, fmt).strftime("%m/%d/%y")
                    except ValueError:
                        pass
        return ""
        
    def _find_invoice_date(self, text):
        text = text or ""
        patterns = [
                    r"Invoice\s+\d+\s+(\d{1,2}/\d{1,2}/\d{4})",
                    r"Date\s*:\s*(\d{2}/\d{2}/\d{4})",
                    r"\bInvoice\s+\d+\s+(\d{1,2}/\d{1,2}/\d{2,4})",
                    r"INVOICE\s+DATE[\s\S]{0,80}?(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
                    r"INVOICE\s+DATE[\s\S]{0,80}?(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\s+\d{5,}",  
                    r"Invoice\s*Date\s*/\s*Time\s*:\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
                ]
  
        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if not m:
                continue

            value = m.group(1).strip()
            value = value.replace("-", "/")

            for fmt in ("%m/%d/%Y", "%m/%d/%y"):
                try:
                    return datetime.strptime(value, fmt).strftime("%m/%d/%Y")
                except ValueError:
                    pass

        return  (datetime.today() - timedelta(days=1)).strftime("%m/%d/%Y")
        
    def _find_total(self, text):
        for pattern in [r"\bTotal\s*[:\-]?\s*[$S8]?\s*([0-9,]+\.\d{2})",
                        r"\bTotal\s*[:\-]?\s*[$S8]?\s*([0-9,]+)",
                        r"Amount\s*due\s*[$8]?\s*([-\d,]+\.\d{2})",
                        r"Total\s+Amount\s+USD[\s\S]{0,80}?\$?\s*([0-9,]+\.\d{2})",
                        r"PLEASE\s+PAY\s*>?\s*THIS\s+TOTAL\s*>?\s*([0-9,]+\.\d{2})", 
                        r"PLEASE\s+PAY[\s\S]{0,120}?([0-9][0-9,\s]*[.]\s*\d\s*\d)",
                        r"Invoice\s+Total\s*:\s*\$?\s*([0-9,]+\.\d{2})",
                        r"Amount\s*Due\s*:\s*[$S8]?\s*([0-9,]+\.\d{2})",
                        r"Total\s+Amount\s+USD\s*\$\s*([\d,]+\.\d{2})",
                        ]:
            matches = re.findall(pattern, text or "", re.IGNORECASE)
            if matches:
                value = matches[-1]
                return value.replace(",", "").replace(" ", "")
        return ""

    def _find_po_number(self, text):
        patterns = [
            r"PO #.*?(\d{4,})",
        ]
        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if m:
                return m.group(1)
        return ""

    def _find_service_center_address(self, text):
        m = re.search(
            r"SERVICE\s+CENTER\s+INFORMATION([\s\S]+?)\b[A-Za-z .'-]+,\s*[A-Z]{2}\s+\d{5}\b",
            text,
            re.IGNORECASE,
        )

        if m:
            return " ".join(m.group(0).split())

        return ""
    def _find_postcode(self, address):
        if not address:
            return ""

        # Normal: CA 95336 or OR 97140-9563
        m = re.search(r"\b[A-Z]{2}\s+(\d{5})(?:-\d{4})?\b", address, re.I)
        if m:
            return m.group(1)

        # OCR merged ZIP: 953363208
        m = re.search(r"\b(\d{5})\d{4}\b", address)
        if m:
            return m.group(1)

        return ""
        
    def _find_ship_to_address(self, text):
        """
        Valvoline uses GUEST INFORMATION as the customer/ship-to address.
        """

        m = re.search(
            r"SHIP\s+TO:.*?(\d+\s+[A-Z0-9\s.#-]+).*?([A-Z\s]+\s+[A-Z]{2}\s+\d{5}(?:-\d{4})?)",
            text,
            re.IGNORECASE,
        )

        if m:
            return " ".join(m.group(1).split())

        return ""
        
    def _find_vendor_address(self, text):
        for pattern in [ r"(\d+\s+[A-Z0-9\s]+)\s+([A-Z\s]+,\s*CA\s*\d{5})",
                          r"(?:jiffy\s*lube|jiffylube|jefflube)[\s\S]*?(\d+\s+[^\n]+)[\s\S]*?([A-Z\s]+,\s*[A-Z]{2}\s*\d{5,9})",
        ]:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(2)
        return ""
