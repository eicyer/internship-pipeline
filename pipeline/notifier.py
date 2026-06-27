import os

import requests


def _score_bar(score, total: int = 10) -> str:
    try:
        filled = max(0, min(int(score), total))
    except (TypeError, ValueError):
        return "?"
    return "🟩" * filled + "⬜" * (total - filled)


def send_telegram(job, analysis: dict, sheet_url: str = "") -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    score = analysis.get("fit_score", "?")
    grad_flag = "YES" if analysis.get("grad_flag") else "NO"
    skills_list = analysis.get("skills_matched", [])
    skills = " · ".join(skills_list) if skills_list else "—"

    bar = _score_bar(score)

    ranked = analysis.get("ranked_experiences", [])
    exp_lines = []
    for i, exp in enumerate(ranked[:3], 1):
        bullets = exp.get("optimized_bullets", [])
        if not bullets:
            continue
        exp_lines.append(f"*{i}. {exp['company']}* ({exp['role']})")
        for b in bullets:
            exp_lines.append(f'  • "{b}"')

    divider = "━━━━━━━━━━━━━━━━━━━━━━"

    text = (
        f"{divider}\n"
        f"🆕 *{job.company}* — {job.role}\n"
        f"📍 {job.location} · [Apply Now]({job.apply_link})\n"
        f"{divider}\n"
        f"⭐ Fit: {bar} {score}/10\n"
        f"🎓 Grad required: {grad_flag}\n"
        f"✅ {skills}"
    )

    if exp_lines:
        text += "\n\n💼 *Top experiences to highlight:*\n" + "\n".join(exp_lines)

    if sheet_url:
        text += f"\n\n[📊 Open in Sheets →]({sheet_url})"

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


def send_run_summary(stats: dict) -> None:
    """Send a single pipeline run summary message to Telegram."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return

    logged = stats.get("logged", 0)
    new_jobs = stats.get("new_jobs", 0)
    stage1 = stats.get("stage1", 0)
    scored = stats.get("scored", 0)
    above = stats.get("above_threshold", 0)

    drop_parts = []
    if stats.get("dropped_low_fit", 0):
        drop_parts.append(f"{stats['dropped_low_fit']}× low fit")
    if stats.get("dropped_grad_flag", 0):
        drop_parts.append(f"{stats['dropped_grad_flag']}× grad flag")
    if stats.get("dropped_both", 0):
        drop_parts.append(f"{stats['dropped_both']}× both")

    outcome = f"✅ {logged} logged to Sheets" if logged else "ℹ️ No new matches this run"

    text = (
        f"📋 *Pipeline Run Complete*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 {new_jobs} new jobs found\n"
        f"✂️ {stage1} passed Stage 1 (keyword filter)\n"
        f"📊 {scored} scored by Haiku\n"
        f"⬆️ {above} cleared threshold\n"
        f"{outcome}"
    )
    if drop_parts:
        text += f"\n🚫 Dropped: {' · '.join(drop_parts)}"

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    resp = requests.post(url, json=payload, timeout=10)
    if not resp.ok:
        print(f"Telegram error (summary): {resp.status_code} {resp.text}")
