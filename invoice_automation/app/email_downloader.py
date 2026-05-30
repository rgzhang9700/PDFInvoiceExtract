import imaplib
import email
from pathlib import Path
from email.header import decode_header


def download_invoice_pdfs_for_accounts(email_config, client_root):
    accounts = email_config.get("accounts", [])

    for account in accounts:
        if not account.get("enabled", True):
            continue

        print(f"Checking email account: {account.get('name', account.get('email_user'))}")
        download_invoice_pdfs_for_account(account, client_root)


def download_invoice_pdfs_for_account(account_cfg, client_root):
    mail = imaplib.IMAP4_SSL(account_cfg["imap_server"])
    mail.login(account_cfg["email_user"], account_cfg["email_password"])
    mail.select(account_cfg.get("mailbox", "INBOX"))

    search_query = account_cfg.get("search_query", '(UNSEEN)')
    status, messages = mail.search(None, search_query)

    if status != "OK":
        print("No matching emails found.")
        mail.logout()
        return

    for msg_id in messages[0].split():
        status, msg_data = mail.fetch(msg_id, "(RFC822)")
        if status != "OK":
            continue

        msg = email.message_from_bytes(msg_data[0][1])
        subject = decode_mime_header(msg.get("Subject", ""))
        sender = decode_mime_header(msg.get("From", ""))

        for part in msg.walk():
            filename = part.get_filename()
            if not filename:
                continue

            filename = decode_mime_header(filename)

            if not filename.lower().endswith(".pdf"):
                continue

            target_folder = choose_download_folder(
                rules=account_cfg.get("rules", []),
                sender=sender,
                subject=subject,
                filename=filename,
                client_root=client_root,
                default_folder=account_cfg.get("unknown_folder", "./downloads/UNKNOWN"),
            )

            target_folder.mkdir(parents=True, exist_ok=True)
            filepath = unique_path(target_folder / filename)

            with open(filepath, "wb") as f:
                f.write(part.get_payload(decode=True))

            print(f"Downloaded: {filepath}")

        if account_cfg.get("mark_seen", True):
            mail.store(msg_id, "+FLAGS", "\\Seen")

    mail.logout()


def choose_download_folder(rules, sender, subject, filename, client_root, default_folder):
    sender_l = sender.lower()
    subject_l = subject.lower()
    filename_l = filename.lower()

    for rule in rules:
        if rule_matches(rule, sender_l, subject_l, filename_l):
            return resolve_path(client_root, rule["download_folder"])

    return resolve_path(client_root, default_folder)


def rule_matches(rule, sender_l, subject_l, filename_l):
    checks = []

    if rule.get("from_contains"):
        checks.append(rule["from_contains"].lower() in sender_l)

    if rule.get("subject_contains"):
        checks.append(rule["subject_contains"].lower() in subject_l)

    if rule.get("filename_contains"):
        checks.append(rule["filename_contains"].lower() in filename_l)

    if rule.get("subject_not_contains"):
        checks.append(rule["subject_not_contains"].lower() not in subject_l)

    match_type = rule.get("match", "any").lower()

    if not checks:
        return False

    if match_type == "all":
        return all(checks)

    return any(checks)


def decode_mime_header(value):
    parts = decode_header(value)
    decoded = ""

    for part, encoding in parts:
        if isinstance(part, bytes):
            decoded += part.decode(encoding or "utf-8", errors="ignore")
        else:
            decoded += part

    return decoded


def resolve_path(client_root, path_value):
    p = Path(path_value)
    if p.is_absolute() or ":" in str(path_value):
        return p
    return client_root / p


def unique_path(path):
    path = Path(path)
    if not path.exists():
        return path

    counter = 1
    while True:
        candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1