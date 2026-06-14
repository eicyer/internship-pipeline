from config import SKILLS, EXPERIENCES


def parse_resume(_path=None) -> tuple[str, list[dict]]:
    skills_str = ", ".join(SKILLS)
    return skills_str, EXPERIENCES
