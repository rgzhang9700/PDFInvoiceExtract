from pathlib import Path
from datetime import datetime
import yaml

from app.email_downloader import download_invoice_pdfs_for_accounts
from app.pdf_text import extract_pdf_text
from app.file_mover import move_processed_pdf, move_failed_pdf
from app.logger import ProcessingLogger
from app.duplicate_checker import InvoiceHistory

from app.parsers.generic_parser import GenericParser
from app.parsers.valvoline_parser import ValvolineParser
from app.parsers.fleetpride_parser import FleetPrideParser
from app.excel_writer import write_invoices_to_vendor_template_batches


PARSERS = {
    "generic": GenericParser(),
    "valvoline": ValvolineParser(),
    "fleetpride": FleetPrideParser(),
}


def run_client(config_path: Path):
    config_path = Path(config_path)
    client_root = config_path.parent

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    logger = ProcessingLogger(resolve_path(client_root, config["logging"]["log_folder"]), config["logging"])
    history = InvoiceHistory(resolve_path(client_root, config["history"]["database_file"]))

    if config.get("email", {}).get("enabled", False):
        download_invoice_pdfs_for_accounts(
            email_config=config["email"],
            client_root=client_root
        )

    grand_total_found = 0
    grand_success = 0
    grand_failed = 0
    grand_duplicate = 0

    for vendor_folder, vendor_config in config["vendors"].items():
        invoices, summary = parse_vendor_folder(
            vendor_folder=vendor_folder,
            vendor_config=vendor_config,
            processing_config=config["processing"],
            client_root=client_root,
            logger=logger,
            history=history,
        )

        grand_total_found += summary["total_files_found"]
        grand_success += summary["success_count"]
        grand_failed += summary["failed_count"]
        grand_duplicate += summary["duplicate_count"]

        if invoices:
            write_invoices_to_vendor_template_batches(
                invoices=invoices,
                vendor_config=vendor_config,
                excel_config=config["excel"],
                client_root=client_root,
            )

    print("===================================")
    print(f"CLIENT: {config.get('client', {}).get('name', 'Unknown')}")
    print("RUN TOTAL")
    print(f"Total files found: {grand_total_found}")
    print(f"Success: {grand_success}")
    print(f"Failed: {grand_failed}")
    print(f"Duplicate skipped: {grand_duplicate}")
    print(f"Total invoice files processed: {grand_success + grand_failed + grand_duplicate}")
    print("===================================")


def parse_vendor_folder(vendor_folder, vendor_config, processing_config, client_root, logger, history):
    parser_name = vendor_config.get("parser", "generic")
    parser = PARSERS.get(parser_name, GenericParser())

    input_folder = resolve_path(client_root, vendor_config["input_folder"])
    pdf_files = sorted(input_folder.glob("*.pdf"))

    summary = {
        "total_files_found": len(pdf_files),
        "success_count": 0,
        "failed_count": 0,
        "duplicate_count": 0,
    }

    invoices = []

    if not pdf_files:
        logger.write_run_summary({
            "run_time": datetime.now().isoformat(timespec="seconds"),
            "vendor_folder": vendor_folder,
            "total_files_found": 0,
            "success_count": 0,
            "failed_count": 0,
            "duplicate_count": 0,
            "total_invoice_files_processed": 0,
        })
        return invoices, summary

    for pdf_file in pdf_files:
        print(f"Processing {vendor_folder}: {pdf_file.name}")

        try:
            text, pdf_type = extract_pdf_text(pdf_file)
            invoice = parser.parse(text)
            print(invoice)

            invoice["vendor_folder"] = vendor_folder
            invoice["pdf_type"] = pdf_type
            invoice["pdf_file"] = pdf_file.name
            invoice["status"] = "success"
            invoice["error"] = ""

            # FIX:
            # Use the PDF filename as part of the duplicate key.
            # This prevents blank invoice_number/date/amount from making different PDFs look duplicate.
            invoice_key = history.make_invoice_key(
                vendor_folder=vendor_folder,
                invoice_number=invoice.get("invoice_number", ""),
                amount=invoice.get("amount", ""),
                invoice_date=invoice.get("invoice_date", ""),
                pdf_file=pdf_file.name,
            )

            if history.exists(invoice_key):
                summary["duplicate_count"] += 1
                invoice["status"] = "duplicate_skipped"
                invoice["error"] = "Duplicate invoice detected"
                logger.write_error({
                    "vendor_folder": vendor_folder,
                    "pdf_file": pdf_file.name,
                    "processed_file_path": "",
                    "status": "duplicate_skipped",
                    "error": "Duplicate invoice detected",
                })
                continue

            moved_path = ""
            if processing_config.get("move_processed", True):
                moved_path = move_processed_pdf(
                    pdf_file=pdf_file,
                    vendor_folder=vendor_folder,
                    processed_root=resolve_path(client_root, processing_config.get("processed_folder", "./processed")),
                    append_timestamp_if_exists=processing_config.get("append_timestamp_if_exists", True),
                )

            invoice["processed_file_path"] = moved_path
            invoices.append(invoice)
            logger.write_success(invoice)
            history.add(invoice_key, invoice)

            summary["success_count"] += 1

        except Exception as e:
            summary["failed_count"] += 1

            moved_path = ""
            if processing_config.get("move_failed", True):
                moved_path = move_failed_pdf(
                    pdf_file=pdf_file,
                    vendor_folder=vendor_folder,
                    failed_root=resolve_path(client_root, processing_config.get("failed_folder", "./error")),
                    append_timestamp_if_exists=processing_config.get("append_timestamp_if_exists", True),
                )

            logger.write_error({
                "vendor_folder": vendor_folder,
                "pdf_file": pdf_file.name,
                "processed_file_path": moved_path,
                "status": "failed",
                "error": str(e),
            })
            print(f"FAILED {pdf_file.name}: {e}")

    logger.write_run_summary({
        "run_time": datetime.now().isoformat(timespec="seconds"),
        "vendor_folder": vendor_folder,
        "total_files_found": summary["total_files_found"],
        "success_count": summary["success_count"],
        "failed_count": summary["failed_count"],
        "duplicate_count": summary["duplicate_count"],
        "total_invoice_files_processed": summary["success_count"] + summary["failed_count"] + summary["duplicate_count"],
    })

    return invoices, summary


def resolve_path(client_root, path_value):
    p = Path(path_value)
    if p.is_absolute() or ":" in str(path_value):
        return p
    return client_root / p