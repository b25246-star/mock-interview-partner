import re
from pathlib import Path

import yaml

from llm import chat_json, load_prompt
from models import Evaluation, Report, SampleAnswer

FILLERS = ["um", "uh", "like", "basically", "actually", "you know", "kind of", "sort of", "literally"]


def _rubric_text() -> str:
    data = yaml.safe_load((Path(__file__).parent / "rubric.yaml").read_text(encoding="utf-8"))
    lines = ["Criteria:"]
    lines += [f"- {c['name']}: {c['description']}" for c in data["criteria"]]
    lines.append("\nScore anchors:")
    lines += [f"{k} = {v}" for k, v in data["anchors"].items()]
    return "\n".join(lines)


def filler_stats(answer: str) -> dict:
    text = answer.lower()
    words = re.findall(r"[a-zA-Z']+", text)
    counts = {f: len(re.findall(rf"\b{re.escape(f)}\b", text)) for f in FILLERS}
    counts = {k: v for k, v in counts.items() if v}
    return {"words": len(words), "fillers": counts}


def evaluate_answer(profile, question: str, good_points: list[str], answer: str) -> Evaluation:
    system = load_prompt("evaluator.txt").format(rubric=_rubric_text())
    user = (
        f"QUESTION: {question}\n"
        f"A GOOD ANSWER INCLUDES: {'; '.join(good_points) or 'n/a'}\n\n"
        f"CANDIDATE ANSWER: {answer or '(no answer)'}\n\n"
        f"CANDIDATE PROFILE:\n{profile.model_dump_json(indent=2)}"
    )
    return chat_json(system, user, Evaluation)


def make_sample_answer(profile, question: str, good_points: list[str], answer: str) -> str:
    user = (
        f"QUESTION: {question}\n"
        f"A GOOD ANSWER INCLUDES: {'; '.join(good_points) or 'n/a'}\n"
        f"WHAT THE CANDIDATE SAID: {answer or '(no answer)'}\n\n"
        f"CANDIDATE PROFILE:\n{profile.model_dump_json(indent=2)}"
    )
    return chat_json(load_prompt("sample.txt"), user, SampleAnswer).sample_answer


def final_report(profile, role: str, turns: list[dict]) -> Report:
    transcript = "\n\n".join(
        f"[{t['type']}{' follow-up' if t['followup'] else ''}] Q: {t['question']}\n"
        f"A: {t['answer']}\nScore: {t['eval']['score']}/5 | Fix: {t['eval']['to_fix']}"
        for t in turns
    )
    user = f"TARGET ROLE: {role}\n\nINTERVIEW TRANSCRIPT WITH SCORES:\n{transcript}"
    return chat_json(load_prompt("report.txt"), user, Report)