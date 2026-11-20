# Kakao → Drive → ORION intake

This bridge is optional and disabled when bot-side Drive credentials are absent.
ChatGPT's connected Drive session is independent of a GitHub Actions runner.
Do not publish the source folder, copy chat text into Git, or treat a successful
unit test as an authenticated live deployment.

## Runtime

- `news_engine.get_us_news` reads only TXT children of the fixed ORION folder.
- The TXT header must match `[정보방] 미국 주식 뉴스 공장` exactly.
- Bootstrap compares the acknowledged baseline file and considers only previously
  unseen posts from the last hour. Later scans admit unseen posts within 36 hours.
- The breaking worker stores IDs and unresolved public original links inside its
  existing serialized `orion-alert-state` checkpoint, before Telegram requests.
  No sender names or message bodies are persisted. The morning job is stateless
  and uses the bootstrap rule; the breaking worker owns durable intake tracking.
- Exact canonical URL matches to NVIDIA newsroom and PR Newswire RSS remain
  eligible. Supported public original pages can also be retrieved directly:
  Reuters, NVIDIA newsroom/IR, Micron IR, Intel newsroom, Coherent IR, Anthropic
  and Lumentum. The page must contain an Article/NewsArticle structured record
  with matching original URL, a full articleBody and timezone-aware datePublished
  within 36 hours. Search snippets, descriptions and dateModified are insufficient.
  This verifies publication metadata, not the financial truth of every claim.
  Access denials, redirects, unsupported layouts and linkless posts stay unverified.
  No access-wall bypass or arbitrary redirect/short-link traversal is attempted.
- Direct-page requests are bounded to two unique URLs per scan and 2 MiB per
  response, with finite timeouts. Attempt counts rotate retries so one inaccessible
  newest URL cannot starve older pending links. No chat bodies/sender names are
  added to the checkpoint, and originals never inherit chat posting time.
- Confirmed records retain the original title, summary and publication time.
  Kakao posting time is separate metadata. No score bonus is awarded for a chat
  mention; existing event, company, finance and chart gates still apply.
- Confirmed originals bypass the general feed selection cap. Same-URL reposts
  contribute at most one article, and existing event dedup handles event repeats.
- Missing credentials, wrong rooms and transport failures are explicit diagnostic
  states. A stale export alone does not prove missing chat posts.

## One-time authenticated setup (not completed by this code change)

Use a Google OAuth client under the owner's control with Drive API enabled and
an offline user grant for `https://www.googleapis.com/auth/drive.readonly`.
This is an account-wide read scope; the implementation restricts requests to the
named folder, but OAuth itself is not folder-scoped. Do not reuse or request
ChatGPT connector tokens.

Store the resulting values as GitHub Actions repository secrets:

- `ORION_DRIVE_CLIENT_ID`
- `ORION_DRIVE_CLIENT_SECRET`
- `ORION_DRIVE_REFRESH_TOKEN`

Do not paste credentials into chat, source files or PR comments. Google OAuth
apps left in external testing can have short-lived grants; configure the app's
publishing/access policy appropriately before unattended use.

Official references:
- https://developers.google.com/workspace/drive/api/reference/rest/v3/files/list
- https://developers.google.com/identity/protocols/oauth2/web-server#offline

## Acceptance before calling it connected

1. Configure the secrets and deploy the reviewed change.
2. Confirm the runtime diagnostic is `ok`, not `not_configured` or `error`.
3. Observe an actual newly posted message in a later export, preserving its KST
   posting time; unchanged chat contents are not a failure.
4. Confirm an eligible original RSS record reaches the existing analysis engine;
   an unknown/linkless claim must stay pending. A second scan must add zero leads.
5. Only then verify a real qualified event through normal alert delivery. No test
   message should be sent merely to demonstrate the bridge.

Tests run without Drive credentials or external Telegram delivery:
`python -m unittest test_kakao_news_source test_kakao_drive_bridge test_kakao_original_source test_primary_news test_feeder_news test_breaking_news test_breaking_quality`

## 2026-11-20 intake incident and coverage measurement

A read-only replay of the acknowledged 11:01 KST export failed in `parse_export`
with `ValueError: Invalid IPv6 URL`. One malformed URL in a cumulative export
prevented all posts from being parsed, including otherwise valid new posts.
URL extraction now skips malformed authorities/ports and credential-bearing
links individually, preserving message text, IDs and posting times.

After the fix, the same real export parsed 8,718 messages through 10:58 KST.
Its November 20 non-media posts numbered 186: 60 contained usable links and
126 had none. Zero of those 60 posts linked to either currently supported RSS
host. This is a coverage measurement, not an investment signal or proof that
bot-side credentials are configured. Private chat bodies are not committed.

At the time of that measurement the bridge was not a general research/verification system.
Unsupported publishers and linkless leads require a separate verification
queue; they must not be silently described as analyzed stocks or rejected
investment opportunities. Broadening that coverage requires source-specific
original retrieval, publication-time verification and deduplication tests.
Weekly research reports have no automatic code-application path in this bridge;
any claimed implementation must identify a change, its validation and deployment.
