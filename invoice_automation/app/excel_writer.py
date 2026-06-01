from pathlib import Path
import shutil
import math
from datetime import datetime
import openpyxl


def write_invoices_to_vendor_template_batches(invoices, vendor_config, excel_config, client_root):
    template_file = resolve_path(client_root, vendor_config["template_file"])
    output_folder = resolve_path(client_root, vendor_config["output_folder"])
    output_folder.mkdir(parents=True, exist_ok=True)

    if not template_file.exists():
        raise FileNotFoundError(f"Vendor Excel template not found: {template_file}")

    if not invoices:
        print("No invoices to write.")
        return

    max_records = int(excel_config.get("max_records_per_file", 50))
    file_prefix = vendor_config.get("file_prefix", "invoice_load")
    total_batches = math.ceil(len(invoices) / max_records)

    for batch_index in range(total_batches):
        batch_records = invoices[batch_index * max_records:(batch_index + 1) * max_records]
        output_file = output_folder / f"{file_prefix}_{batch_index + 1:03d}.xlsx"

        shutil.copy(template_file, output_file)

        wb = openpyxl.load_workbook(output_file)
        sheet_name = excel_config.get("sheet_name", "Data")

        if sheet_name not in wb.sheetnames:
            raise ValueError(f"Sheet '{sheet_name}' not found in vendor template: {template_file}")

        ws = wb[sheet_name]
        header_row = find_header_row(ws)
        headers = build_header_map(ws, header_row)
        start_row = find_next_empty_row(ws, header_row + 1)

        for index, invoice in enumerate(batch_records):
            row = start_row + index

            # FIX:
            # Invoice/row ID increases 1, 2, 3 within each Excel output file.
            line_number = index + 1

            write_invoice_row(
                ws=ws,
                row=row,
                headers=headers,
                invoice=invoice,
                vendor_config=vendor_config,
                excel_config=excel_config,
                line_number=line_number,
            )

        wb.save(output_file)
        print(f"Excel created: {output_file} with {len(batch_records)} records")


def write_processing_summary_excel(successful_records, failed_records, output_file):
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    wb = openpyxl.Workbook()

    success_ws = wb.active
    success_ws.title = "Successful Parses"
    success_headers = [
        "filename",
        "invoice_number",
        "invoice_date",
        "total_amount",
        "post_code",
        "vendor_folder",
        "vendor_name",
        "status",
    ]
    success_ws.append(success_headers)

    for record in successful_records:
        success_ws.append([
            record.get("pdf_file", ""),
            record.get("invoice_number", ""),
            record.get("invoice_date", ""),
            record.get("amount", ""),
            get_invoice_post_code(record),
            record.get("vendor_folder", ""),
            record.get("vendor_name", ""),
            record.get("status", ""),
        ])

    failed_ws = wb.create_sheet("Failed Parses")
    failed_headers = ["filename", "vendor_folder", "status", "error", "processed_file_path"]
    failed_ws.append(failed_headers)

    for record in failed_records:
        failed_ws.append([
            record.get("pdf_file", ""),
            record.get("vendor_folder", ""),
            record.get("status", "failed"),
            record.get("error", ""),
            record.get("processed_file_path", ""),
        ])

    for ws in (success_ws, failed_ws):
        for column_cells in ws.columns:
            max_length = max(
                len(str(cell.value)) if cell.value is not None else 0
                for cell in column_cells
            )
            ws.column_dimensions[column_cells[0].column_letter].width = min(max_length + 2, 60)

    wb.save(output_file)
    print(f"Processing summary Excel created: {output_file}")


def get_invoice_post_code(invoice):
    for key in (
        "ship_to_postcode",
        "service_center_postcode",
        "vendor_postcode",
        "post_code",
        "postcode",
    ):
        value = invoice.get(key, "")
        if value:
            return value
    return ""


def find_header_row(ws):
    for row in range(1, ws.max_row + 1):
        values = [
            str(ws.cell(row=row, column=col).value).strip()
            for col in range(1, ws.max_column + 1)
            if ws.cell(row=row, column=col).value is not None
        ]

        if "COMPANYCODE" in values and "SUPPLIERINVOICEIDBYINVCGPARTY" in values:
            return row

    raise ValueError(
        "Header row not found. Template must contain COMPANYCODE and SUPPLIERINVOICEIDBYINVCGPARTY."
    )


def build_header_map(ws, header_row):
    headers = {}

    for col in range(1, ws.max_column + 1):
        value = ws.cell(row=header_row, column=col).value

        if value is not None:
            header = str(value).strip()

            # Keep first instance if duplicated.
            if header and header not in headers:
                headers[header] = col

    return headers


def find_next_empty_row(ws, start_row, key_column=1):
    row = start_row

    while ws.cell(row=row, column=key_column).value not in (None, ""):
        row += 1

    return row


def set_if_exists(ws, row, headers, header_name, value):
    col = headers.get(header_name)

    if col:
        ws.cell(row=row, column=col).value = value

def set_date_if_exists(ws, row, headers, header_name, value):
    col = headers.get(header_name)

    if not col:
        return

    cell = ws.cell(row=row, column=col)

    try:
        if isinstance(value, str):
            dt = datetime.strptime(value, "%Y-%m-%d")
            cell.value = dt
        else:
            cell.value = value

        cell.number_format = "MM/DD/YYYY"
    except Exception:
        cell.value = value


def write_invoice_row(ws, row, headers, invoice, vendor_config, excel_config, line_number):
    amount = invoice.get("amount", "")
    invoice_date = invoice.get("invoice_date") or datetime.today().strftime("%m/%d/%y")
    posting_date = datetime.today().strftime("%m/%d/%y")
    TaxCenterID = invoice.get("TaxCenterID", "")
    # Always write column A so the record is visible.
    ws.cell(row=row, column=1).value = line_number

    # Also write to any known ID headers if they exist.
    set_if_exists(ws, row, headers, "SUPPLIERINVOICEITEM", line_number)
    set_if_exists(ws, row, headers, "INVOICEID", line_number)
    set_if_exists(ws, row, headers, "ITEMID", line_number)
    if "Valvoline" in invoice.get("vendor_name",""):
        set_if_exists(ws, row, headers, "V03884")
    else:
        set_if_exists(ws, row, headers, "COMPANYCODE", vendor_config.get("company_code", ""))
    set_if_exists(ws, row, headers, "SUPPLIERINVOICETRANSACTIONTYPE", excel_config.get("supplier_invoice_transaction_type", "1"), )
    set_if_exists(ws, row, headers, "INVOICINGPARTY", vendor_config.get("vendor_code", ""))
    set_if_exists(ws, row, headers, "SUPPLIERINVOICEIDBYINVCGPARTY", invoice.get("invoice_number", ""))
    set_date_if_exists(ws, row, headers, "DOCUMENTDATE", invoice_date)
    set_date_if_exists(ws, row, headers, "POSTINGDATE", posting_date)
    set_if_exists(ws, row, headers, "ACCOUNTINGDOCUMENTTYPE", excel_config.get("accounting_document_type", "NS"))
    set_if_exists(ws, row, headers,"ACCOUNTINGDOCUMENTHEADERTEXT", f"{invoice.get('vendor_name', '')} Invoice {invoice.get('invoice_number', '')}",)
    set_if_exists(ws, row, headers, "DOCUMENTCURRENCY", excel_config.get("document_currency", "USD"))
    set_if_exists(ws, row, headers, "INVOICEGROSSAMOUNT", amount)

    set_if_exists(ws, row, headers, "GLACCOUNT", vendor_config.get("gl_account", ""))
    set_if_exists(ws, row, headers, "DEBITCREDITCODE", "S")
    set_if_exists(ws, row, headers, "SUPPLIERINVOICEITEMAMOUNT", amount)
    set_if_exists(ws, row, headers, "TAXCODE", vendor_config.get("tax_code", ""))
    set_if_exists(ws, row, headers, "SUPPLIERINVOICEITEMTEXT", vendor_config.get("item_text", ""))
    set_if_exists(ws, row, headers, "TAXJURISDICTION", TaxCenterID)
    set_if_exists(ws, row, headers, "COSTCENTER", vendor_config.get("cost_center", ""))
    set_if_exists(ws, row, headers, "DOCUMENTITEMTEXT", vendor_config.get("item_text", ""))
    ws.cell(row=row,column=71).value = vendor_config.get("company_code", "")


def resolve_path(client_root, path_value):
    p = Path(path_value)

    if p.is_absolute() or ":" in str(path_value):
        return p

    return client_root / p