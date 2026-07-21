# 🤖 Bible SMS Bot

Texts a daily King James Version Bible verse to a fixed list of phone numbers
via free carrier email-to-SMS gateways (no Twilio, no paid SMS API). Runs
once a day at 8:00 AM from the Mac via LaunchAgent.

- Verse bank: `verses.json` — ~165 curated encouraging verses (KJV, public
  domain), fetched once from bible-api.com. No network needed at runtime to
  pick the verse; rotation is deterministic by calendar day (cycles through
  all verses, no repeats within a cycle).
- Recipients: `recipients.json` (gitignored) — edit anytime, E.164 numbers
  plus each person's carrier (see `CARRIER_GATEWAYS` in `bible_sms.py` for
  the supported list).
- Delivery: sends a plain email to `<10-digit-number>@<carrier-gateway>`
  (e.g. `6045551234@msg.telus.com`) — the carrier relays it as a real text.
  Free, but not guaranteed: carriers can filter or rate-limit these
  gateways, and there's no delivery confirmation.
- Failures: retried 3x with progressive backoff, then a Telegram alert is
  sent to Bryan only.

## One-time setup

1. Pick (or create) a Gmail account to send from — a free dedicated account
   for this bot is safer than using your personal one. Turn on 2-Step
   Verification, then generate an App Password at
   myaccount.google.com/apppasswords.
2. `cp .env.example .env` and fill in `SMTP_EMAIL` / `SMTP_APP_PASSWORD`.
   Optionally add the Telegram bot token for failure alerts.
3. `cp recipients.example.json recipients.json` and fill in real names,
   E.164 numbers, and each person's carrier.
4. Confirm you have the recipient's carrier right — a wrong carrier means
   the text silently never arrives. If unsure, ask them or check a recent
   bill.
5. Test without sending:
   `/Library/Frameworks/Python.framework/Versions/3.14/bin/python3 bible_sms.py --dry-run`
6. Real test to one phone:
   `... bible_sms.py --to +1YOURNUMBER --carrier telus`
7. Install the daily 8 AM schedule:
   ```
   cp com.bryanrana.biblesms.plist ~/Library/LaunchAgents/
   launchctl load -w ~/Library/LaunchAgents/com.bryanrana.biblesms.plist
   ```

Logs: `~/Library/Logs/biblesms.log`

## Notes

- The plist assumes the folder lives at `/Users/bryanrana/bible_sms` (repo
  root = home dir). Adjust paths if it moves to the droplet (use a systemd
  timer there instead).
- Carrier gateways are run by the carriers, not us, and occasionally change
  or shut down. If a recipient stops getting texts, first check whether
  their carrier's gateway is still working before assuming the bot broke.
- Some carriers throttle or spam-filter mail from unfamiliar senders more
  aggressively at first — expect the first few days' deliverability to be
  the real test, not just the one manual `--to` send.
- To change send time, edit Hour/Minute in the plist, then
  `launchctl unload` + `launchctl load -w` it again.
