# Kakao research intake

`kakao_news_source.py` reads an explicitly supplied export of `[정보방] 미국 주식 뉴스 공장`. It preserves multiline text, links and KST posting timestamps, checks the exact room, and assigns stable message IDs across cumulative exports. `select_new_posts` excludes media placeholders, old/future posts and known messages. Checkpoint IDs only after the caller has durably accepted the posts.

These records are research leads (`publication_verified=False`), not eligible news articles or stock recommendations. A future bot adapter must fetch and verify original news/public disclosures before feeding them to event and company validation. Posting time does not establish article publication time. This module does not fetch links, send messages, or change existing news selection.

The connected ChatGPT Drive reader is authenticated separately from GitHub Actions. No runtime credential, public sharing link, or live bot adapter is configured by this change. A separate hourly ChatGPT task reads the private Drive folder for new information; it does not connect the Telegram bot. The Windows exporter remains a separate 5-minute process.

Validation: `python -m unittest test_kakao_news_source -v`. Tests cover Korean encodings, multiline messages, exact room checks, timestamps, media and system entries, and repeated export deduplication. A local read-only run against the user's private export parsed 2,399 messages and returned zero new messages on repeat intake. Private export content is not committed.
