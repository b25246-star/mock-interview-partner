from pathlib import Path

from llm import chat_json, load_prompt
from models import FollowUp

# Every .txt in prompts/personas/ becomes a persona. Add your own file to add one.
PERSONAS = {
    p.stem.replace("_", " ").title(): p.read_text(encoding="utf-8")
    for p in sorted((Path(__file__).parent / "prompts" / "personas").glob("*.txt"))
}


def decide_followup(question: str, answer: str, persona: str) -> FollowUp:
    system = load_prompt("followup.txt").format(persona=persona)
    user = f"QUESTION: {question}\n\nCANDIDATE ANSWER: {answer}"
    return chat_json(system, user, FollowUp)