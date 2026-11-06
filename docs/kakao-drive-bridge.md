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
- Only exact canonical URL matches to the supported issuer/publisher RSS records
  (NVIDIA newsroom and PR Newswire) are eligible for the analysis engine. This
  verifies a publication record, not the financial truth of every issuer claim.
  Other links and linkless posts remain unverified and cannot generate a signal.
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
`python -m unittest test_kakao_news_source test_kakao_drive_bridge test_primary_news test_feeder_news test_breaking_news test_breaking_quality`
