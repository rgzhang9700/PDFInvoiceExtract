import re


def find_us_zip(text):
    m = re.search(r"\b\d{5}(?:-\d{4})?\b", text or "")
    return m.group(0) if m else ""


def clean_address(lines):
    return ", ".join([line.strip() for line in lines if line and line.strip()])


def find_address_near_keyword(text, keyword, max_lines=6):
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if keyword.lower() in line.lower():
            block = lines[i + 1:i + 1 + max_lines]
            address = clean_address(block)
            return address, find_us_zip(address)
    return "", ""


def find_first_city_state_zip_block(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for i, line in enumerate(lines):
        if re.search(r"\b[A-Z][A-Za-z .'-]+,\s*[A-Z]{2}\s+\d{5}", line):
            block = lines[max(0, i - 2):i + 1]
            address = clean_address(block)
            return address, find_us_zip(address)
    return "", ""