from llm import chat_json, load_prompt
from models import Plan


def build_plan(profile, role: str, jd: str, persona: str, n: int, avoid: list[str],
               focus: str = "Balanced mix", level: str = "Fresher / campus"):
    system = load_prompt("planner.txt").format(persona=persona)
    avoid_text = "\n".join(f"- {q}" for q in avoid[-30:]) or "none"
    user = (
        f"TARGET ROLE: {role}\n"
        f"JOB DESCRIPTION: {jd or 'not provided'}\n"
        f"NUMBER OF QUESTIONS: {n}\n"
        f"CANDIDATE LEVEL: {level}\n"
        f"INTERVIEW FOCUS: {focus} (shift the question mix toward this focus, "
        f"but still begin with the intro question)\n\n"
        f"CANDIDATE PROFILE (JSON):\n{profile.model_dump_json(indent=2)}\n\n"
        f"DO NOT REPEAT THESE PAST QUESTIONS:\n{avoid_text}"
    )
    plan = chat_json(system, user, Plan)
    return plan.questions[:n]