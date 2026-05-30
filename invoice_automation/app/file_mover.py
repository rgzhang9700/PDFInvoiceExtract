from pathlib import Path
from datetime import datetime
import shutil


def move_processed_pdf(pdf_file, vendor_folder, processed_root, append_timestamp_if_exists=True):
    target_folder = Path(processed_root) / vendor_folder
    return move_file(pdf_file, target_folder, append_timestamp_if_exists)


def move_failed_pdf(pdf_file, vendor_folder, failed_root, append_timestamp_if_exists=True):
    target_folder = Path(failed_root) / vendor_folder
    return move_file(pdf_file, target_folder, append_timestamp_if_exists)


def move_file(pdf_file, target_folder, append_timestamp_if_exists=True):
    pdf_file = Path(pdf_file)
    target_folder = Path(target_folder)
    target_folder.mkdir(parents=True, exist_ok=True)

    target_file = target_folder / pdf_file.name

    if target_file.exists() and append_timestamp_if_exists:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_file = target_folder / f"{pdf_file.stem}_{timestamp}{pdf_file.suffix}"

    shutil.move(str(pdf_file), str(target_file))
    return str(target_file)