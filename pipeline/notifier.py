import os

import requests


def _escape(text: str) -> str:
    """Escape Telegram MarkdownV2 special characters."""
    for ch in r"\_*[]()~`>#+-=|{}.!":
        text = text.replace(ch, f"\\{ch}")
    return text


def send_telegram(job, analysis: dict, sheet_url: str = "") -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    score = analysis.get("fit_score", "?")
    grad_flag = "YES" if analysis.get("grad_flag") else "NO"
    skills = ", ".join(analysis.get("skills_matched", [])) or "—"
    bullets = analysis.get("bullet_suggestions", [])

    bullet_lines = "\n".join(f'• "{b}"' for b in bullets)
    sheets_link = f"\n\n[Open in Sheets →]({sheet_url})" if sheet_url else ""

    text = (
        f"🆕 *{job.company}* — {job.role}\n"
        f"📍 {job.location} | 🔗 [Apply]({job.apply_link})\n"
        f"⭐ Fit: {score}/10 | 🎓 Grad flag: {grad_flag}\n"
        f"✅ Skills match: {skills}"
    )
    if bullet_lines:
        text += f"\n\n💡 *Bullet suggestions:*\n{bullet_lines}"
    text += sheets_link

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
