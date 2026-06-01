import unittest
from datetime import datetime

import openpyxl

from invoice_automation.app.excel_writer import set_if_exists, write_invoice_row


class ExcelWriterTests(unittest.TestCase):
    def test_set_if_exists_defaults_missing_value_to_blank(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        headers = {"OPTIONALFIELD": 1}

        set_if_exists(ws, 2, headers, "OPTIONALFIELD")

        self.assertEqual(ws.cell(row=2, column=1).value, "")

    def test_write_invoice_row_writes_transaction_type(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        header_names = [
            "SUPPLIERINVOICEITEM",
            "INVOICEID",
            "ITEMID",
            "COMPANYCODE",
            "SUPPLIERINVOICETRANSACTIONTYPE",
            "INVOICINGPARTY",
            "SUPPLIERINVOICEIDBYINVCGPARTY",
            "DOCUMENTDATE",
            "POSTINGDATE",
            "ACCOUNTINGDOCUMENTTYPE",
            "ACCOUNTINGDOCUMENTHEADERTEXT",
            "DOCUMENTCURRENCY",
            "INVOICEGROSSAMOUNT",
            "GLACCOUNT",
            "DEBITCREDITCODE",
            "SUPPLIERINVOICEITEMAMOUNT",
            "TAXCODE",
            "SUPPLIERINVOICEITEMTEXT",
            "TAXJURISDICTION",
            "COSTCENTER",
            "DOCUMENTITEMTEXT",
        ]
        for col, name in enumerate(header_names, start=1):
            ws.cell(row=1, column=col).value = name
        headers = {name: col for col, name in enumerate(header_names, start=1)}

        write_invoice_row(
            ws=ws,
            row=2,
            headers=headers,
            invoice={
                "amount": "123.45",
                "invoice_date": "2026-05-31",
                "invoice_number": "INV-1",
                "vendor_name": "Vendor",
                "TaxCenterID": "TX001",
            },
            vendor_config={
                "company_code": "1000",
                "vendor_code": "V100",
                "gl_account": "5000",
                "tax_code": "I0",
                "item_text": "Repairs",
                "cost_center": "CC100",
            },
            excel_config={
                "supplier_invoice_transaction_type": "2",
                "accounting_document_type": "NS",
                "document_currency": "USD",
            },
            line_number=1,
        )

        self.assertEqual(
            ws.cell(row=2, column=headers["SUPPLIERINVOICETRANSACTIONTYPE"]).value,
            "2",
        )
        self.assertEqual(
            ws.cell(row=2, column=headers["SUPPLIERINVOICEIDBYINVCGPARTY"]).value,
            "INV-1",
        )
        self.assertEqual(
            ws.cell(row=2, column=headers["INVOICEGROSSAMOUNT"]).value,
            "123.45",
        )
        self.assertIsInstance(
            ws.cell(row=2, column=headers["DOCUMENTDATE"]).value,
            datetime,
        )


if __name__ == "__main__":
    unittest.main()
