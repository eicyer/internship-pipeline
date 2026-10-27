# Apply-link redirector (Cloudflare Worker)

Makes "Apply Now" (Telegram) and the Sheet's Link column go **straight to the job
posting** in one click, while still auto-flipping the row's Status to `Applied`.

```
click → Worker ──302──▶ job posting
           └── background ping ──▶ Apps Script (appscript/click_tracker.gs) → Status = Applied
```

## One-time setup (free Cloudflare account)

1. Deploy `appscript/click_tracker.gs` as a Web App if you haven't already (see the
   comment at the top of that file). If you already have it deployed, paste the
   updated file in and publish a new version: Deploy → Manage deployments → edit →
   Version: New version. Copy the `/exec` URL.
2. Deploy the Worker, using either option below:
   - **Dashboard:** Cloudflare dashboard → Workers & Pages → Create → Create Worker →
     name it `apply-redirect` → Deploy → Edit code → paste `worker.js` → Deploy.
     Then Settings → Variables and Secrets → add a text variable `APPS_SCRIPT_URL`
     = the `/exec` URL from step 1.
   - **CLI:** put the `/exec` URL in `wrangler.toml`'s `APPS_SCRIPT_URL`, then
     `cd cloudflare && npx wrangler deploy`.
3. Copy the Worker URL (e.g. `https://apply-redirect.<you>.workers.dev`) and set it as
   the `TRACKING_BASE_URL` GitHub Actions secret, replacing the Apps Script URL.

New jobs logged after step 3 use the Worker. Rows and Telegram messages from before
the switch still point at the Apps Script URL. Those keep working, but still need the
extra click.

Free tier: 100k requests/day.
