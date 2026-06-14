import re
from docx import Document


def parse_resume(path: str = "resume.docx") -> tuple[str, list[str]]:
    """Return (skills_csv, bullet_list) extracted from a .docx resume."""
    doc = Document(path)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

    skills_str = ""
    bullets = []
    in_skills = False
    in_experience = False

    for para in paragraphs:
        lower = para.lower()

        # Detect section headers
        if re.match(r"^(technical\s+)?skills?$", lower):
            in_skills = True
            in_experience = False
            continue
        if re.match(r"^(experience|work experience|projects?)$", lower):
            in_experience = True
            in_skills = False
            continue
        if re.match(r"^(education|certifications?|awards?|publications?)$", lower):
            in_skills = False
            in_experience = False
            continue

        if in_skills and not skills_str:
            skills_str = para
        elif in_experience and para.startswith(("•", "-", "–", "*", "▪")):
            bullets.append(para.lstrip("•-–*▪ ").strip())

    if not skills_str:
        # Fallback: scan for a line containing skill-like comma-separated tokens
        for para in paragraphs:
            if "," in para and len(para) < 300 and re.search(r"\b(Python|Java|SQL|React|AWS|C\+\+)\b", para):
                skills_str = para
                break

    return skills_str, bullets[:10]  # cap bullets at 10 to keep prompts short
