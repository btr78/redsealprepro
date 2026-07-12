#!/usr/bin/env python3
"""🤖 Bible SMS Bot — texts a daily KJV verse to a fixed list of phones via Twilio.

Runs once per day (LaunchAgent on the Mac, or cron/systemd timer on a droplet).
Verses come from the local verses.json (no network needed to pick a verse);
rotation is deterministic by calendar day so every run on the same date sends
the same verse. Sends a Telegram alert to Bryan if any send fails.

Usage:
  bible_sms.py            send today's verse to everyone in recipients.json
  bible_sms.py --dry-run  print what would be sent, send nothing
  bible_sms.py --to +16045551234   send today's verse only to this number
"""

import argparse
import base64
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VERSES_FILE = os.path.join(SCRIPT_DIR, "verses.json")
RECIPIENTS_FILE = os.path.join(SCRIPT_DIR, "recipients.json")
ENV_FILE = os.path.join(SCRIPT_DIR, ".env")

MAX_RETRIES = 3


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


def load_recipients():
    if not os.path.exists(RECIPIENTS_FILE):
        raise RuntimeError(
            f"{RECIPIENTS_FILE} not found — copy recipients.example.json and edit it"
        )
    with open(RECIPIENTS_FILE) as f:
        recipients = json.load(f)
    valid = [r for r in recipients if r.get("number", "").startswith("+")]
    if len(valid) != len(recipients):
        raise RuntimeError("every recipient number must be E.164 format, e.g. +16045551234")
    return valid


def send_sms(to_number, body):
    """Send one SMS through Twilio's REST API with progressive-backoff retries."""
    sid = os.environ["TWILIO_ACCOUNT_SID"]
    token = os.environ["TWILIO_AUTH_TOKEN"]
    from_number = os.environ["TWILIO_FROM_NUMBER"]

    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    data = urllib.parse.urlencode({"To": to_number, "From": from_number, "Body": body}).encode()
    auth = base64.b64encode(f"{sid}:{token}".encode()).decode()

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        req = urllib.request.Request(url, data=data, headers={"Authorization": f"Basic {auth}"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode())
            return result.get("sid", "?")
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:300]
            last_error = f"HTTP {e.code}: {detail}"
            # 4xx (bad number, bad credentials) won't succeed on retry
            if 400 <= e.code < 500:
                break
        except Exception as e:
            last_error = str(e)
        wait = 5 * 2 ** (attempt - 1)
        log(f"  attempt {attempt} to {to_number} failed ({last_error}), retrying in {wait}s")
        time.sleep(wait)
    raise RuntimeError(f"giving up on {to_number}: {last_error}")


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
    args = parser.parse_args()

    load_env()
    verse = todays_verse()
    message = build_message(verse)
    log(f"today's verse: {verse['ref']}")

    if args.to:
        recipients = [{"name": "override", "number": args.to}]
    else:
        recipients = load_recipients()

    if args.dry_run:
        print("----- message -----")
        print(message)
        print("----- recipients -----")
        for r in recipients:
            print(f"  {r.get('name', '?')}: {r['number']}")
        return

    missing = [k for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER")
               if not os.environ.get(k)]
    if missing:
        raise RuntimeError(f"missing in .env: {', '.join(missing)}")

    failures = []
    for r in recipients:
        try:
            sid = send_sms(r["number"], message)
            log(f"sent to {r.get('name', '?')} ({r['number']}) sid={sid}")
        except Exception as e:
            log(f"FAILED for {r.get('name', '?')} ({r['number']}): {e}")
            failures.append(f"{r.get('name', '?')} ({r['number']}): {e}")
        time.sleep(1)  # stay well under Twilio's 1 msg/sec long-code limit

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
