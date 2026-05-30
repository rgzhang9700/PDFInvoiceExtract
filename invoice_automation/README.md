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
- Total invoice files processed
- Processed/error folder movement
- Duplicate invoice detection using SQLite
- EXE-ready with PyInstaller

## Run sample client

```bash
pip install -r requirements.txt
python run_client.py --client-config clients/sample_client/config.yaml
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