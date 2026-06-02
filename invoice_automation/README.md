# Invoice Automation Full Project v4

This version supports:

- Multiple accounting firm/client configs
- Shared drive folder locations
- Email routing rules by sender/subject/filename
- Vendor-specific Excel templates
- Default SAP/template fields only
- 50 records max per Excel output file
- Real PDF vs scanned image PDF auto-detection
- EasyOCR OCR fallback
- Success, error, and run summary logs
- Summary Excel workbook for successful and failed PDF parses
- Total invoice files processed
- Processed/error folder movement
- Duplicate invoice detection using SQLite
- EXE-ready with PyInstaller

## Run sample client

```bash
pip install -r requirements.txt
python run_client.py --client-config clients/sample_client/config.yaml
```


## Parse summary Excel

Every run creates a parse summary workbook in the configured logging folder by default. The workbook contains:

- `Successful Parses`: filename, invoice number, invoice date, total amount, post code, vendor folder, vendor name, and parse status.
- `Failed Parses`: filename, vendor folder, status, error, and the failed/error folder path when the PDF was moved.

Optional config can override the output location or filename:

```yaml
summary_excel:
  folder: ./logs
  filename_prefix: invoice_parse_summary
  # filename: latest_invoice_parse_summary.xlsx
```

## Shared drive config

Use:

```text
clients/sample_client/config_shared_drive_example.yaml
```

Example paths:

```yaml
input_folder: "G:/Shared drives/AP Invoices/FLEETPRIDE"
template_file: "G:/Shared drives/AP Templates/FLEETPRIDE/fleetpride_template.xlsx"
output_folder: "G:/Shared drives/AP Output/FLEETPRIDE"
```

## Email routing

Each email rule downloads PDF attachments to a vendor folder:

```yaml
rules:
  - vendor: "FLEETPRIDE"
    from_contains: "fleetpride"
    subject_contains: "fleetpride"
    filename_contains: "fleetpride"
    download_folder: "./downloads/FLEETPRIDE"
```


## Email-to-G-drive append workflow

To poll email, save incoming invoice PDFs to a shared/G-drive folder, parse them,
and append each parsed invoice as a new row in one output workbook, run the same
client command on a cloud schedule such as every 5 minutes. Configure email
rules so their `download_folder` points at the G-drive input folder, configure
the matching vendor `input_folder` to the same location, and set Excel
`output_mode` to `append` with an `output_file` on the G drive:

```yaml
email:
  enabled: true
  accounts:
    - name: AP inbox
      imap_server: imap.example.com
      email_user: ap@example.com
      email_password: your_app_password
      search_query: '(UNSEEN)'
      mark_seen: true
      rules:
        - vendor: OILVENDOR
          subject_contains: invoice
          download_folder: "G:/Shared drives/AP Invoices/OILVENDOR"

vendors:
  OILVENDOR:
    input_folder: "G:/Shared drives/AP Invoices/OILVENDOR"
    template_file: "G:/Shared drives/AP Templates/InvoiceTemplate.xlsx"
    output_folder: "G:/Shared drives/AP Output"
    output_file: "G:/Shared drives/AP Output/invoice_output.xlsx"

excel:
  output_mode: append
  sheet_name: Data
```

With `output_mode: append`, the workbook is created from the vendor template the
first time it is needed. Later runs open the same output workbook, find the next
empty row, and append only the new parsed invoice records.

## Build EXE

```bat
build_exe.bat
```

Then run:

```bat
dist\InvoiceProcessor.exe --client-config clients\sample_client\config.yaml
```

## Client model

For multiple accounting firms:

```text
clients/
  firm_a/config.yaml
  firm_b/config.yaml
  firm_c/config.yaml
```

Use the same codebase for every firm. Only the config, templates, and folders change.