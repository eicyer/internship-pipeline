// Click-to-apply redirector (Cloudflare Worker).
//
// Apps Script Web Apps can't send a real HTTP redirect — their HTML runs in a
// sandboxed iframe that blocks automatic top-level navigation, which forced an
// extra "Open the job posting" click. This Worker sits in front instead:
//
//   GET /?link=<apply_link>
//     1. responds immediately with a 302 to <apply_link>
//     2. in the background, pings the Apps Script (APPS_SCRIPT_URL) with
//        ?link=<apply_link>&mode=mark so it flips the row's Status to Applied
//
// Deploy steps: see cloudflare/README.md.

export default {
  async fetch(request, env, ctx) {
    const link = new URL(request.url).searchParams.get("link") || "";

    let dest;
    try {
      dest = new URL(link);
    } catch {
      return new Response("Missing or invalid ?link=", { status: 400 });
    }
    // Only forward to real web pages — never javascript:, data:, etc.
    if (dest.protocol !== "https:" && dest.protocol !== "http:") {
      return new Response("Unsupported link", { status: 400 });
    }

    if (env.APPS_SCRIPT_URL) {
      const mark = new URL(env.APPS_SCRIPT_URL);
      mark.searchParams.set("link", link);
      mark.searchParams.set("mode", "mark");
      // Never block or break the redirect just because the sheet update failed.
      ctx.waitUntil(fetch(mark.toString()).catch(() => {}));
    }

    return Response.redirect(dest.toString(), 302);
  },
};
