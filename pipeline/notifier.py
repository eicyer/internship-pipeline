import os

import requests


def send_telegram(job, analysis: dict, sheet_url: str = "") -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    score = analysis.get("fit_score", "?")
    grad_flag = "YES" if analysis.get("grad_flag") else "NO"
    skills = ", ".join(analysis.get("skills_matched", [])) or "—"

    # Build experience sections for top 3 ranked matches
    ranked = analysis.get("ranked_experiences", [])
    exp_lines = []
    for exp in ranked[:3]:
        bullets = exp.get("optimized_bullets", [])
        if not bullets:
            continue
        exp_lines.append(f"*{exp['company']}* ({exp['role']})")
        for b in bullets:
            exp_lines.append(f'  • "{b}"')

    text = (
        f"🆕 *{job.company}* — {job.role}\n"
        f"📍 {job.location} | 🔗 [Apply]({job.apply_link})\n"
        f"⭐ Fit: {score}/10 | 🎓 Grad flag: {grad_flag}\n"
        f"✅ Skills match: {skills}"
    )
    if exp_lines:
        text += "\n\n💡 *Top experiences to highlight:*\n" + "\n".join(exp_lines)
    if sheet_url:
        text += f"\n\n[Open in Sheets →]({sheet_url})"

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    resp = requests.post(url, json=payload, timeout=10)
    if not resp.ok:
        print(f"Telegram error: {resp.status_code} {resp.text}")
