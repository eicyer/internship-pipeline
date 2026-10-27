// One-time setup (Google Apps Script, deployed as a Web App):
//
//   1. Open the Google Sheet used by this pipeline.
//   2. Extensions -> Apps Script.
//   3. Replace the default Code.gs contents with this file, and set
//      SPREADSHEET_ID below to the same value as the GOOGLE_SHEET_ID secret.
//   4. Deploy -> New deployment -> type "Web app".
//        - Execute as: Me
//        - Who has access: Anyone
//   5. Copy the deployment's /exec URL into the Cloudflare Worker's
//      APPS_SCRIPT_URL (see cloudflare/README.md). TRACKING_BASE_URL should
//      point at the Worker, not here: Apps Script can't issue a real redirect,
//      so linking here directly costs an extra click.
//
// What it does: every apply link the pipeline sends (Telegram + the Sheet's
// Link column) is wrapped to point here first. A click looks up the job by
// its raw apply_link in column E, flips Status (column F) from "To Apply" to
// "Applied" if that's still its value, then redirects the browser on to the
// real posting.

const SPREADSHEET_ID = '1noR9ahhlH-JDm-kZlB-7wd7xyuMpM23kvgWsyklEMVwzwrNoR47XpLwb'; // same value as the GOOGLE_SHEET_ID secret
const SHEET_NAME = 'Sheet1';
const LINK_COL = 5;   // E
const STATUS_COL = 6; // F

function doGet(e) {
  var link = (e.parameter && e.parameter.link) || '';

  if (link) {
    try {
      markApplied_(link);
    } catch (err) {
      // Never block the redirect just because the sheet update failed.
    }
  }

  // Background ping from the Cloudflare Worker (cloudflare/worker.js), which
  // already redirected the user — just acknowledge, no page to render.
  if (e.parameter && e.parameter.mode === 'mark') {
    return ContentService.createTextOutput('ok');
  }

  // Legacy path: links that point here directly (rows logged before the
  // Worker was set up) still get the one-click interstitial below.
  var dest = link || 'https://www.google.com';
  // Apps Script serves HtmlService output inside a sandboxed iframe on
  // googleusercontent.com, so a plain meta-refresh / window.location only
  // navigates that inner iframe — most job sites refuse to be framed, leaving
  // you stuck on the script.google.com page. The redirect has to target the
  // top window. The sandbox may block automatic top navigation (it requires a
  // user gesture), so the link below also targets _top as a one-click fallback.
  return HtmlService.createHtmlOutput(
    '<html><head><base target="_top"></head>' +
    '<body style="font-family:sans-serif;text-align:center;margin-top:20vh">' +
    '<p>Redirecting to the job posting…</p>' +
    '<a href="' + escapeHtml_(dest) + '" target="_top" style="font-size:20px">Open the job posting &rarr;</a>' +
    '<script>try { window.top.location.href = ' + JSON.stringify(dest) + '; } catch (e) {}</script>' +
    '</body></html>'
  );
}

function markApplied_(link) {
  var sheet = SpreadsheetApp.openById(SPREADSHEET_ID).getSheetByName(SHEET_NAME);
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return;

  var links = sheet.getRange(2, LINK_COL, lastRow - 1, 1).getValues();
  for (var i = 0; i < links.length; i++) {
    if (links[i][0] === link) {
      var statusCell = sheet.getRange(i + 2, STATUS_COL);
      if (statusCell.getValue() === 'To Apply') {
        statusCell.setValue('Applied');
      }
      break;
    }
  }
}

function escapeHtml_(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
