// One-time setup (Google Apps Script, deployed as a Web App):
//
//   1. Open the Google Sheet used by this pipeline.
//   2. Extensions -> Apps Script.
//   3. Replace the default Code.gs contents with this file, and set
//      SPREADSHEET_ID below to the same value as the GOOGLE_SHEET_ID secret.
//   4. Deploy -> New deployment -> type "Web app".
//        - Execute as: Me
//        - Who has access: Anyone
//   5. Copy the deployment's /exec URL and set it as the TRACKING_BASE_URL
//      secret (GitHub Actions) / env var (local runs).
//
// What it does: every apply link the pipeline sends (Telegram + the Sheet's
// Link column) is wrapped to point here first. A click looks up the job by
// its raw apply_link in column E, flips Status (column F) from "To Apply" to
// "Applied" if that's still its value, then redirects the browser on to the
// real posting.

const SPREADSHEET_ID = 'PUT_YOUR_GOOGLE_SHEET_ID_HERE'; // same value as the GOOGLE_SHEET_ID secret
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

  var dest = link || 'https://www.google.com';
  return HtmlService.createHtmlOutput(
    '<html><head><meta http-equiv="refresh" content="0; url=' + escapeHtml_(dest) + '"></head>' +
    '<body>Redirecting… <a href="' + escapeHtml_(dest) + '">Click here if you are not redirected</a>' +
    '<script>window.location.replace(' + JSON.stringify(dest) + ');</script>' +
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
