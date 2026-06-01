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
from app.parsers.jiffy_lube_parser import JiffyLubeParser
from app.excel_writer import (
    write_invoices_to_vendor_template_batches,
    write_processing_summary_excel,
)


PARSERS = {
    "generic": GenericParser,
    "valvoline": ValvolineParser,
    "fleetpride": FleetPrideParser,
    "jiffylube": JiffyLubeParser,
    "jiffy_lube": JiffyLubeParser,
}


def detect_parser(text, default_parser_name="generic"):
    """
    Auto-detect parser from OCR/PDF text.

    Important:
    This only changes which parser reads the PDF.
    Excel output still uses the vendor folder config, for example OILVENDOR.
    """

    upper_text = (text or "").upper()

    if "VALVOLINE" in upper_text or "VIOC" in upper_text:
        return ValvolineParser()

    if "JIFFY LUBE" in upper_text or "JIFFYLUBE" in upper_text:
        return JiffyLubeParser()

    if "MYFLEETCENTER" in upper_text or "MY FLEET CENTER" in upper_text:
        return JiffyLubeParser()

    if "FLEETPRIDE" in upper_text:
        return FleetPrideParser()

    parser_class = PARSERS.get(default_parser_name, GenericParser)
    return parser_class()


def run_client(config_path: Path):
    config_path = Path(config_path)
    client_root = config_path.parent

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    logger = ProcessingLogger(
        resolve_path(client_root, config["logging"]["log_folder"]),
        config["logging"],
    )
    history = InvoiceHistory(resolve_path(client_root, config["history"]["database_file"]))

    # Config switch:
    # duplicate_check: true   -> skip invoices already in history
    # duplicate_check: false  -> allow reprocessing same invoices during testing
    duplicate_check = config.get("duplicate_check", True)

    if config.get("email", {}).get("enabled", False):
        download_invoice_pdfs_for_accounts(
            email_config=config["email"],
            client_root=client_root,
        )

    grand_total_found = 0
    grand_success = 0
    grand_failed = 0
    grand_duplicate = 0

    # One Excel file per run: collect all invoices first, then write once.
    all_invoices = []
    successful_parse_records = []
    failed_parse_records = []
    output_vendor_config = None
    vendor_summaries = {}

    for vendor_folder, vendor_config in config["vendors"].items():
        invoices, successful_records, failed_records, summary = parse_vendor_folder(
            vendor_folder=vendor_folder,
            vendor_config=vendor_config,
            processing_config=config["processing"],
            client_root=client_root,
            logger=logger,
            history=history,
            duplicate_check=duplicate_check,
        )

        vendor_summaries[vendor_folder] = summary
        grand_total_found += summary["total_files_found"]
        grand_failed += summary["failed_count"]
        grand_duplicate += summary["duplicate_count"]
        successful_parse_records.extend(successful_records)
        failed_parse_records.extend(failed_records)

        if invoices:
            all_invoices.extend(invoices)

            # All vendors use the same template. Use the first vendor config
            # as the output/template/GL config for this run.
            if output_vendor_config is None:
                output_vendor_config = vendor_config

    summary_excel_file = build_processing_summary_excel_path(
        config=config,
        client_root=client_root,
    )

    try:
        write_processing_summary_excel(
            successful_records=successful_parse_records,
            failed_records=failed_parse_records,
            output_file=summary_excel_file,
        )
    except Exception as e:
        print(f"PROCESSING SUMMARY EXCEL WRITE FAILED: {e}")

    if all_invoices:
        try:
            write_invoices_to_vendor_template_batches(
                invoices=all_invoices,
                vendor_config=output_vendor_config,
                excel_config=config["excel"],
                client_root=client_root,
            )

            # Move PDFs only after the single Excel write succeeds.
            moved_by_vendor = move_successful_invoices_after_excel(
                invoices=all_invoices,
                vendor_folder="ALL_VENDORS",
                processing_config=config["processing"],
                client_root=client_root,
                logger=logger,
                history=history,
            )

            for vendor_folder, moved_count in moved_by_vendor.items():
                if vendor_folder in vendor_summaries:
                    vendor_summaries[vendor_folder]["success_count"] += moved_count
                grand_success += moved_count

        except Exception as e:
            print(f"EXCEL WRITE FAILED for one-file run: {e}")

            # Do not move PDFs to processed if Excel failed.
            # Leave them in input folder so they can be fixed/reprocessed.
            for invoice in all_invoices:
                logger.write_error({
                    "vendor_folder": invoice.get("vendor_folder", ""),
                    "pdf_file": invoice.get("pdf_file", ""),
                    "processed_file_path": "",
                    "status": "excel_failed_not_moved",
                    "error": str(e),
                })

    for vendor_folder, summary in vendor_summaries.items():
        logger.write_run_summary({
            "run_time": datetime.now().isoformat(timespec="seconds"),
            "vendor_folder": vendor_folder,
            "total_files_found": summary["total_files_found"],
            "success_count": summary["success_count"],
            "failed_count": summary["failed_count"],
            "duplicate_count": summary["duplicate_count"],
            "total_invoice_files_processed": (
                summary["success_count"]
                + summary["failed_count"]
                + summary["duplicate_count"]
            ),
        })

    print("===================================")
    print(f"CLIENT: {config.get('client', {}).get('name', 'Unknown')}")
    print("RUN TOTAL")
    print(f"Total files found: {grand_total_found}")
    print(f"Success: {grand_success}")
    print(f"Failed: {grand_failed}")
    print(f"Duplicate skipped: {grand_duplicate}")
    print(f"Total invoice files processed: {grand_success + grand_failed + grand_duplicate}")
    print("===================================")


def build_processing_summary_excel_path(config, client_root):
    summary_config = config.get("summary_excel", {})
    folder = resolve_path(
        client_root,
        summary_config.get(
            "folder",
            config.get("logging", {}).get("log_folder", "./logs"),
        ),
    )
    filename = summary_config.get("filename")

    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename_prefix = summary_config.get("filename_prefix", "invoice_parse_summary")
        filename = f"{filename_prefix}_{timestamp}.xlsx"

    return folder / filename


def parse_vendor_folder(
    vendor_folder,
    vendor_config,
    processing_config,
    client_root,
    logger,
    history,
    duplicate_check=True,
):
    default_parser_name = vendor_config.get("parser", "generic")

    input_folder = resolve_path(client_root, vendor_config["input_folder"])
    pdf_files = sorted(input_folder.glob("*.pdf"))

    summary = {
        "total_files_found": len(pdf_files),
        "success_count": 0,
        "failed_count": 0,
        "duplicate_count": 0,
    }

    invoices = []
    successful_records = []
    failed_records = []

    if not pdf_files:
        return invoices, successful_records, failed_records, summary

    for pdf_file in pdf_files:
        print(f"Processing {vendor_folder}: {pdf_file.name}")

        try:
            text, pdf_type = extract_pdf_text(pdf_file)

            parser = detect_parser(text, default_parser_name=default_parser_name)
            print(f"Using parser: {parser.__class__.__name__}")

            invoice = parser.parse(text)
            print(invoice)

            invoice["vendor_folder"] = vendor_folder
            invoice["pdf_type"] = pdf_type
            invoice["pdf_file"] = pdf_file.name
            invoice["source_pdf_path"] = str(pdf_file)
            invoice["status"] = "parsed_waiting_for_excel"
            invoice["error"] = ""

            validate_invoice(invoice)

            invoice_key = history.make_invoice_key(
                vendor_folder=vendor_folder,
                invoice_number=invoice.get("invoice_number", ""),
                amount=invoice.get("amount", ""),
                invoice_date=invoice.get("invoice_date", ""),
                pdf_file=pdf_file.name,
            )

            invoice["invoice_key"] = invoice_key

            successful_records.append(invoice.copy())

            if duplicate_check and history.exists(invoice_key):
                summary["duplicate_count"] += 1
                invoice["status"] = "duplicate_skipped"
                invoice["error"] = "Duplicate invoice detected"

                successful_records[-1]["status"] = "duplicate_skipped"
                successful_records[-1]["error"] = "Duplicate invoice detected"

                logger.write_error({
                    "vendor_folder": vendor_folder,
                    "pdf_file": pdf_file.name,
                    "processed_file_path": "",
                    "status": "duplicate_skipped",
                    "error": "Duplicate invoice detected",
                })
                continue

            # Do not move to processed here.
            # The PDF stays in input until Excel write succeeds.
            invoices.append(invoice)

        except Exception as e:
            summary["failed_count"] += 1

            moved_path = ""
            if processing_config.get("move_failed", True):
                moved_path = move_failed_pdf(
                    pdf_file=pdf_file,
                    vendor_folder=vendor_folder,
                    failed_root=resolve_path(
                        client_root,
                        processing_config.get("failed_folder", "./error"),
                    ),
                    append_timestamp_if_exists=processing_config.get(
                        "append_timestamp_if_exists",
                        True,
                    ),
                )

            failed_record = {
                "vendor_folder": vendor_folder,
                "pdf_file": pdf_file.name,
                "processed_file_path": moved_path,
                "status": "failed",
                "error": str(e),
            }
            failed_records.append(failed_record)

            logger.write_error(failed_record)
            print(f"FAILED {pdf_file.name}: {e}")

    return invoices, successful_records, failed_records, summary


def move_successful_invoices_after_excel(
    invoices,
    vendor_folder,
    processing_config,
    client_root,
    logger,
    history,
):
    moved_by_vendor = {}

    for invoice in invoices:
        pdf_file = Path(invoice["source_pdf_path"])
        invoice_vendor_folder = invoice.get("vendor_folder", vendor_folder)

        moved_path = ""

        if processing_config.get("move_processed", True):
            moved_path = move_processed_pdf(
                pdf_file=pdf_file,
                vendor_folder=invoice_vendor_folder,
                processed_root=resolve_path(
                    client_root,
                    processing_config.get("processed_folder", "./processed"),
                ),
                append_timestamp_if_exists=processing_config.get(
                    "append_timestamp_if_exists",
                    True,
                ),
            )

        invoice["processed_file_path"] = moved_path
        invoice["status"] = "success"
        invoice["error"] = ""

        logger.write_success(invoice)
        history.add(invoice["invoice_key"], invoice)

        moved_by_vendor[invoice_vendor_folder] = moved_by_vendor.get(invoice_vendor_folder, 0) + 1

    return moved_by_vendor


def validate_invoice(invoice):
    required_fields = [
        "invoice_number",
        "invoice_date",
        "amount",
    ]

    missing = [field for field in required_fields if not invoice.get(field)]

    if missing:
        raise ValueError(f"Missing required fields: {missing}")

    try:
        amount = float(invoice.get("amount", 0))
        if amount <= 0:
            raise ValueError(f"Invalid invoice amount: {amount}")
    except Exception:
        raise ValueError(f"Invalid invoice amount: {invoice.get('amount')}")


def resolve_path(client_root, path_value):
    p = Path(path_value)

    if p.is_absolute() or ":" in str(path_value):
        return p

    return client_root / p
