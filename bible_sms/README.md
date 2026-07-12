# 🤖 Bible SMS Bot

Texts a daily King James Version Bible verse to a fixed list of phone numbers
via Twilio SMS. Runs once a day at 8:00 AM from the Mac via LaunchAgent.

- Verse bank: `verses.json` — ~165 curated encouraging verses (KJV, public
  domain), fetched once from bible-api.com. No network needed at runtime to
  pick the verse; rotation is deterministic by calendar day (cycles through
  all verses, no repeats within a cycle).
- Recipients: `recipients.json` (gitignored) — edit anytime, E.164 numbers.
- Failures: retried 3x with progressive backoff, then a Telegram alert is
  sent to Bryan only.

## One-time setup

1. Create a Twilio account at twilio.com, buy a Canadian local number
   (~$1.15 USD/mo; SMS ~$0.0079 each).
2. `cp .env.example .env` and fill in the Twilio SID, auth token, and the
   Twilio number. Optionally add the Telegram bot token for failure alerts.
3. `cp recipients.example.json recipients.json` and put in the real names
   and numbers.
4. Test without sending:
   `/Library/Frameworks/Python.framework/Versions/3.14/bin/python3 bible_sms.py --dry-run`
5. Real test to one phone:
   `... bible_sms.py --to +1YOURNUMBER`
6. Install the daily 8 AM schedule:
   ```
   cp com.bryanrana.biblesms.plist ~/Library/LaunchAgents/
   launchctl load -w ~/Library/LaunchAgents/com.bryanrana.biblesms.plist
   ```

Logs: `~/Library/Logs/biblesms.log`

## Notes

- The plist assumes the folder lives at `/Users/bryanrana/bible_sms` (repo
  root = home dir). Adjust paths if it moves to the droplet (use a systemd
  timer there instead).
- Canadian long-code numbers don't need US A2P 10DLC registration for
  low-volume personal messaging.
- To change send time, edit Hour/Minute in the plist, then
  `launchctl unload` + `launchctl load -w` it again.
