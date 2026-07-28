#!/usr/bin/env python3
"""🤖 Bible SMS Bot — texts a daily KJV verse to a fixed list of phones via
free carrier email-to-SMS gateways (no paid SMS API).

Runs once per day (LaunchAgent on the Mac, or cron/systemd timer on a droplet).
Verses come from the local verses.json (no network needed to pick a verse);
rotation is deterministic by calendar day so every run on the same date sends
the same verse. Sends a Telegram alert to Bryan if any send fails.

How it works: each recipient's phone number + carrier maps to an email
address (e.g. 6045551234@msg.telus.com). Sending a plain email to that
address gets relayed by the carrier as a real text message — free, but
deliverability isn't guaranteed and depends on the carrier's gateway staying
up (see CARRIER_GATEWAYS below).

Usage:
  bible_sms.py                     send today's verse to everyone in recipients.json
  bible_sms.py --dry-run           print what would be sent, send nothing
  bible_sms.py --to +16045551234 --carrier telus   send only to this number
"""

import argparse
import datetime
import json
import os
import re
import smtplib
import sys
import time
import urllib.parse
import urllib.request
from email.mime.text import MIMEText

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VERSES_FILE = os.path.join(SCRIPT_DIR, "verses.json")
RECIPIENTS_FILE = os.path.join(SCRIPT_DIR, "recipients.json")
ENV_FILE = os.path.join(SCRIPT_DIR, ".env")

MAX_RETRIES = 3

# Email-to-SMS gateway domains. These are run by the carriers themselves, not
# us — most North American carriers have been SHUTTING THESE DOWN industry-wide
# since ~2023 because spammers abused them for smishing. Confirmed dead as of
# 2026-07-28 (DNS has no working mail server, verified by us): Rogers (killed
# 2023, also took down Fido/Freedom/Chatr since they're Rogers-owned), Bell
# (killed 2025-12-31, also took down Virgin Mobile Canada since it's a
# Bell-owned brand — neither txt.virginplus.ca nor vmobile.ca has an MX
# record), Sprint (merged into T-Mobile, gateway gone), AT&T (winding down,
# no MX left). NOTE: "vmobl.com" is Virgin Mobile USA's old domain, NOT
# Virgin Mobile Canada's — that mixup caused a silent misfire on 2026-07-28
# (mail was accepted by the wrong, defunct-but-still-resolving US domain and
# vanished). These entries are DELETED below rather than kept — do not
# re-add them without re-verifying DNS first (`dig MX <domain>`).
# If a recipient on a *surviving* carrier stops getting texts, check that
# carrier's gateway is still up before assuming the bot itself is broken.
CARRIER_GATEWAYS = {
    # Canada — confirmed live MX as of 2026-07-28
    "telus": "msg.telus.com",
    "koodo": "msg.koodomobile.com",
    "public_mobile": "msg.telus.com",
    # United States — confirmed live MX as of 2026-07-28
    "verizon": "vtext.com",
    "tmobile": "tmomail.net",
    "google_fi": "msg.fi.google.com",
    "uscellular": "email.uscc.net",
}


def log(msg):
    print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def load_env():
    """Load KEY=VALUE pairs from .env into os.environ (existing env wins)."""
    if not os.path.exists(ENV_FILE):
        return
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def todays_verse():
    with open(VERSES_FILE) as f:
        verses = json.load(f)
    if not verses:
        raise RuntimeError("verses.json is empty")
    index = datetime.date.today().toordinal() % len(verses)
    return verses[index]


def build_message(verse):
    return f"\U0001F4D6 Daily Verse\n\n“{verse['text']}”\n\n— {verse['ref']} (KJV)"


def to_gateway_address(number, carrier):
    """Turn (+16045551234, 'telus') into 6045551234@msg.telus.com."""
    domain = CARRIER_GATEWAYS.get(carrier)
    if not domain:
        known = ", ".join(sorted(CARRIER_GATEWAYS))
        raise RuntimeError(f"unknown carrier '{carrier}' — known carriers: {known}")
    digits = re.sub(r"\D", "", number)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]  # strip NANP country code
    if len(digits) != 10:
        raise RuntimeError(f"'{number}' isn't a 10-digit NANP number after stripping +1")
    return f"{digits}@{domain}"


def load_recipients():
    if not os.path.exists(RECIPIENTS_FILE):
        raise RuntimeError(
            f"{RECIPIENTS_FILE} not found — copy recipients.example.json and edit it"
        )
    with open(RECIPIENTS_FILE) as f:
        recipients = json.load(f)
    for r in recipients:
        if not r.get("number", "").startswith("+"):
            raise RuntimeError("every recipient number must be E.164 format, e.g. +16045551234")
        if not r.get("carrier"):
            raise RuntimeError(
                f"recipient {r.get('name', '?')} is missing 'carrier' "
                f"(one of: {', '.join(sorted(CARRIER_GATEWAYS))})"
            )
    return recipients


def send_sms(to_number, carrier, body):
    """Send one text via the carrier's email-to-SMS gateway, with retries."""
    to_addr = to_gateway_address(to_number, carrier)
    from_addr = os.environ["SMTP_EMAIL"]
    password = os.environ["SMTP_APP_PASSWORD"]
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "465"))

    msg = MIMEText(body, _charset="utf-8")
    msg["From"] = from_addr
    msg["To"] = to_addr
    # Deliberately no Subject: some carrier gateways prepend it to the text
    # body, which would show up twice.

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with smtplib.SMTP_SSL(host, port, timeout=30) as server:
                server.login(from_addr, password)
                server.sendmail(from_addr, [to_addr], msg.as_string())
            return to_addr
        except smtplib.SMTPRecipientsRefused as e:
            # carrier gateway rejected the address outright — retrying won't help
            raise RuntimeError(f"gateway refused {to_addr}: {e}") from e
        except Exception as e:
            last_error = str(e)
        wait = 5 * 2 ** (attempt - 1)
        log(f"  attempt {attempt} to {to_addr} failed ({last_error}), retrying in {wait}s")
        time.sleep(wait)
    raise RuntimeError(f"giving up on {to_addr}: {last_error}")


def telegram_alert(text):
    """Failure alert to Bryan only; never raises."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    try:
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
        req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data)
        urllib.request.urlopen(req, timeout=15).read()
    except Exception as e:
        log(f"telegram alert failed too: {e}")


def main():
    parser = argparse.ArgumentParser(description="🤖 Bible SMS Bot")
    parser.add_argument("--dry-run", action="store_true", help="print the message, send nothing")
    parser.add_argument("--to", help="send only to this E.164 number instead of recipients.json")
    parser.add_argument("--carrier", help="carrier for --to, e.g. telus, rogers, att, verizon")
    args = parser.parse_args()

    load_env()
    verse = todays_verse()
    message = build_message(verse)
    log(f"today's verse: {verse['ref']}")

    if args.to:
        if not args.carrier:
            raise RuntimeError("--to requires --carrier too")
        recipients = [{"name": "override", "number": args.to, "carrier": args.carrier}]
    else:
        recipients = load_recipients()

    if args.dry_run:
        print("----- message -----")
        print(message)
        print("----- recipients -----")
        for r in recipients:
            addr = to_gateway_address(r["number"], r["carrier"])
            print(f"  {r.get('name', '?')}: {r['number']} -> {addr}")
        return

    missing = [k for k in ("SMTP_EMAIL", "SMTP_APP_PASSWORD") if not os.environ.get(k)]
    if missing:
        raise RuntimeError(f"missing in .env: {', '.join(missing)}")

    failures = []
    for r in recipients:
        try:
            addr = send_sms(r["number"], r["carrier"], message)
            log(f"sent to {r.get('name', '?')} ({r['number']}) via {addr}")
        except Exception as e:
            log(f"FAILED for {r.get('name', '?')} ({r['number']}): {e}")
            failures.append(f"{r.get('name', '?')} ({r['number']}): {e}")
        time.sleep(1)  # be polite to the SMTP server between sends

    if failures:
        telegram_alert("🤖 Bible SMS Bot — send failures today:\n" + "\n".join(failures))
        sys.exit(1)
    log(f"done — {len(recipients)} message(s) sent")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log(f"FATAL: {exc}")
        telegram_alert(f"🤖 Bible SMS Bot — FATAL: {exc}")
        sys.exit(1)
