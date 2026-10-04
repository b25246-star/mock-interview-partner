import copy
import html
import time
from statistics import mean

import streamlit as st

import llm
import storage
from evaluator import evaluate_answer, filler_stats, final_report, make_sample_answer
from interviewer import PERSONAS, decide_followup
from planner import build_plan
from resume_parser import extract_text, parse_profile

st.set_page_config(
    page_title="Mock Interview Partner",
    page_icon="🎤",
    layout="wide",
    initial_sidebar_state="expanded",
)
storage.init()
S = st.session_state

# ------------------------------------------------------------------ constants
ROLES = [
    "Software Developer", "Backend Developer", "Frontend Developer", "Full Stack Developer",
    "Data Analyst", "Data Scientist / ML Engineer", "DevOps / Cloud Engineer",
    "QA / Test Engineer", "Core Engineering", "Business / Consulting", "Other",
]
FOCUS = ["Balanced mix", "Technical heavy", "Resume deep-dive", "HR and behavioral"]
LEVELS = ["Fresher / campus", "1 to 2 years experience", "Advanced"]
PERSONA_MAP = PERSONAS or {"Default": "A professional, fair interviewer."}
BADGE = {"intro": "b-blue", "resume": "b-purple", "technical": "b-green",
         "behavioral": "b-orange", "hr": "b-pink"}

DEFAULTS = {
    "stage": "setup", "profile": None, "plan": [], "qi": 0, "step": 0, "fu_used": 0,
    "current": None, "turns": [], "last": None, "report": None,
    "friend": "", "role": "", "persona": "",
}
for k, v in DEFAULTS.items():
    S.setdefault(k, copy.deepcopy(v))

CSS = """
<style>
.block-container {padding-top: 2.2rem; max-width: 1100px;}
.hero {padding: 1.4rem 1.7rem; border-radius: 16px; margin-bottom: 1.3rem;
       background: linear-gradient(135deg, rgba(79,139,249,.20), rgba(124,92,255,.12));
       border: 1px solid rgba(128,128,128,.25);}
.hero h1 {margin: 0 0 .35rem 0; font-size: 1.9rem; line-height: 1.2;}
.hero p {margin: 0; opacity: .8;}
.qcard {padding: 1.4rem 1.7rem; border-radius: 16px; margin: .5rem 0 1.1rem 0;
        border: 1px solid rgba(128,128,128,.28); background: rgba(128,128,128,.07);}
.qcard .qtext {font-size: 1.3rem; font-weight: 600; line-height: 1.5; margin-top: .7rem;}
.badge {display: inline-block; padding: .18rem .7rem; border-radius: 999px; margin-right: .4rem;
        font-size: .72rem; font-weight: 700; letter-spacing: .04em;}
.b-blue {background: rgba(79,139,249,.2); color: #7FA8FF;}
.b-purple {background: rgba(168,120,255,.2); color: #B9A0FF;}
.b-green {background: rgba(60,200,140,.2); color: #4FD6A0;}
.b-orange {background: rgba(255,170,60,.2); color: #FFB84F;}
.b-pink {background: rgba(255,110,170,.2); color: #FF8DBB;}
.b-red {background: rgba(255,90,90,.2); color: #FF8080;}
.b-grey {background: rgba(150,150,150,.2); color: #AEB4C0;}
[data-testid="stMetric"] {background: rgba(128,128,128,.07); border: 1px solid rgba(128,128,128,.22);
                          padding: .8rem 1rem; border-radius: 12px;}
section[data-testid="stSidebar"] {border-right: 1px solid rgba(128,128,128,.2);}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ------------------------------------------------------------------ helpers
def badge(text: str, cls: str) -> str:
    return f'<span class="badge {cls}">{html.escape(str(text))}</span>'


def score_icon(score: int) -> str:
    return "🟢" if score >= 4 else "🟡" if score == 3 else "🔴"


def hero(title: str, subtitle: str):
    st.markdown(
        f'<div class="hero"><h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p></div>',
        unsafe_allow_html=True,
    )


def bullets(items: list[str]):
    if not items:
        st.caption("Nothing to show.")
    for i in items:
        st.markdown(f"- {i}")


def _name(m):
    if isinstance(m, dict):
        return m.get("model") or m.get("name")
    return getattr(m, "model", None) or getattr(m, "name", None)


@st.cache_data(ttl=20)
def installed_models() -> list[str]:
    try:
        import ollama
        res = ollama.list()
        items = getattr(res, "models", None)
        if items is None and isinstance(res, dict):
            items = res.get("models", [])
        return sorted(n for n in (_name(m) for m in items or []) if n)
    except Exception:
        return []


def q_to_state(q: dict, followup: bool = False) -> dict:
    return {"text": q["question"], "type": q["type"], "good": q["good_answer_includes"],
            "difficulty": q.get("difficulty", ""), "followup": followup}


def advance():
    S.qi += 1
    S.fu_used = 0
    S.step += 1
    if S.qi >= len(S.plan):
        S.stage = "report"
    else:
        S.current = q_to_state(S.plan[S.qi])


def submit(answer: str):
    cur = S.current
    ev = evaluate_answer(S.profile, cur["text"], cur["good"], answer)
    S.turns.append({
        "question": cur["text"], "type": cur["type"], "followup": cur["followup"],
        "answer": answer, "eval": ev.model_dump(), "stats": filler_stats(answer),
    })
    S.last = ev.model_dump()

    if S.fu_used < 2:
        fu = decide_followup(cur["text"], answer, S.persona)
        if fu.needs_followup and fu.followup_question.strip():
            S.fu_used += 1
            S.step += 1
            S.current = {**cur, "text": fu.followup_question.strip(), "followup": True}
            return
    advance()


def reset():
    for k, v in DEFAULTS.items():
        S[k] = copy.deepcopy(v)


def report_markdown() -> str:
    r = S.report
    avg = mean(t["eval"]["score"] for t in S.turns)
    out = ["# Mock Interview Report", "", f"**Candidate:** {S.friend}  ", f"**Role:** {S.role}  ",
           f"**Average score:** {avg:.1f} / 5", "", r["summary"], ""]
    for title, key in [("Strengths", "strengths"), ("Top weaknesses", "weaknesses"),
                       ("Topics to revise", "topics_to_revise"), ("Practice plan", "practice_plan")]:
        out += [f"## {title}"] + [f"- {i}" for i in r[key]] + [""]
    out.append("## Question by question")
    for t in S.turns:
        out += [f"### {t['question']} ({t['eval']['score']}/5)",
                f"**Answer:** {t['answer'] or '(blank)'}  ",
                f"**Done well:** {t['eval']['done_well']}  ",
                f"**Fix:** {t['eval']['to_fix']}", ""]
    return "\n".join(out)


# ------------------------------------------------------------------ sidebar
locked = S.stage != "setup"
with st.sidebar:
    st.markdown("## 🎤 Mock Interviewer")
    st.caption("Private. Local. Open-source.")
    st.divider()

    st.markdown("**Interview settings**")
    models = installed_models() or [llm.MODEL]
    st.selectbox("Model", models, index=models.index(llm.MODEL) if llm.MODEL in models else 0,
                 key="model_choice", disabled=locked,
                 help="Any model you have pulled in Ollama.")
    llm.MODEL = S.model_choice
    persona_name = st.selectbox("Interviewer persona", list(PERSONA_MAP), key="persona_name", disabled=locked)
    focus = st.selectbox("Interview focus", FOCUS, key="focus", disabled=locked)
    level = st.selectbox("Candidate level", LEVELS, key="level", disabled=locked)
    n_questions = st.slider("Main questions", 5, 10, 6, key="n_questions", disabled=locked)

    if S.stage == "interview":
        st.divider()
        st.markdown("**Live session**")
        c1, c2 = st.columns(2)
        c1.metric("Answered", len(S.turns))
        c2.metric("Avg score", f"{mean(t['eval']['score'] for t in S.turns):.1f}" if S.turns else "–")
        if st.button("⏹ End interview now", use_container_width=True):
            S.stage = "report"
            st.rerun()

    if S.stage != "setup":
        st.button("↺ New session", on_click=reset, use_container_width=True)

    who = S.friend or S.get("friend_input", "")
    past = storage.history(who) if who else []
    if past:
        st.divider()
        st.markdown("**Past sessions**")
        for created, avg_score in reversed(past[-5:]):
            st.caption(f"{created}  ·  {avg_score:.1f} / 5")

    st.divider()
    st.caption(f"Running **{llm.MODEL}** locally via Ollama.")

# ------------------------------------------------------------------ setup
if S.stage == "setup":
    hero("Practice interviews that never leave your laptop",
         "Upload a resume, choose a role, and get tailored questions, strict feedback and a progress report.")

    c1, c2 = st.columns(2)
    friend = c1.text_input("Your name", key="friend_input", placeholder="e.g. Rohan")
    role_choice = c2.selectbox("Target role", ROLES, key="role_choice")
    role = c2.text_input("Specify the role", key="role_other") if role_choice == "Other" else role_choice

    resume = st.file_uploader("Resume (PDF or TXT)", type=["pdf", "txt"])
    with st.expander("Add a job description (optional)"):
        jd = st.text_area("Paste the job description", height=120, label_visibility="collapsed")

    ready = bool(friend and role and resume)
    if st.button("Start interview", type="primary", disabled=not ready, use_container_width=True):
        try:
            with st.status("Setting up your interview...", expanded=True) as status:
                t0 = time.time()
                st.write("Reading your resume...")
                profile = parse_profile(extract_text(resume))
                st.write(f"Resume done in {time.time() - t0:.0f}s")
                t1 = time.time()
                st.write("Planning questions...")
                plan = build_plan(profile, role, jd, PERSONA_MAP[persona_name], n_questions,
                                  storage.past_questions(friend), focus, level)
                st.write(f"Questions ready in {time.time() - t1:.0f}s")
                status.update(label="Ready", state="complete")
        except Exception as e:
            st.error(f"Something went wrong: {e}\n\nIs Ollama running and the model pulled?")
            st.stop()
        S.update(
            profile=profile, plan=[q.model_dump() for q in plan], friend=friend, role=role,
            persona=PERSONA_MAP[persona_name], qi=0, step=0, fu_used=0, turns=[], last=None,
            report=None, current=q_to_state(plan[0].model_dump()), stage="interview",
        )
        st.rerun()
    if not ready:
        st.caption("Enter your name, pick a role and upload a resume to begin.")

# ------------------------------------------------------------------ interview
elif S.stage == "interview":
    hero("Interview in progress", f"{S.role}  ·  {persona_name}")
    st.progress(S.qi / len(S.plan), text=f"Question {S.qi + 1} of {len(S.plan)}")

    if S.last:
        with st.expander(f"Feedback on your last answer: {score_icon(S.last['score'])} {S.last['score']}/5",
                         expanded=True):
            st.markdown(f"**Done well:** {S.last['done_well']}")
            st.markdown(f"**Fix:** {S.last['to_fix']}")
            if S.last.get("sample_answer"):
                st.markdown(f"**Stronger answer:** {S.last['sample_answer']}")
            elif st.button("Show a stronger sample answer", key=f"sample_{S.step}"):
                t = S.turns[-1]
                with st.spinner("Writing sample answer..."):
                    text = make_sample_answer(S.profile, t["question"], [], t["answer"])
                S.last["sample_answer"] = text
                t["eval"]["sample_answer"] = text
                st.rerun()

    cur = S.current
    tags = badge(cur["type"].upper(), BADGE.get(cur["type"], "b-blue"))
    if cur["followup"]:
        tags += badge("FOLLOW-UP", "b-red")
    if cur.get("difficulty"):
        tags += badge(cur["difficulty"].upper(), "b-grey")
    st.markdown(
        f'<div class="qcard">{tags}<div class="qtext">{html.escape(cur["text"])}</div></div>',
        unsafe_allow_html=True,
    )

    key = f"ans_{S.step}"
    if hasattr(st, "audio_input"):
        with st.expander("🎙️ Answer by voice (optional)"):
            audio = st.audio_input("Record your answer", key=f"aud_{S.step}")
            if audio and st.button("Use recording", key=f"use_{S.step}"):
                try:
                    from voice import transcribe
                    with st.spinner("Transcribing..."):
                        S[key] = transcribe(audio.getvalue())
                except ImportError:
                    st.warning("Install faster-whisper to use voice answers.")

    answer = st.text_area("Your answer", key=key, height=190,
                          placeholder="Type your answer here, or record it above...")
    c1, c2, _ = st.columns([2, 1, 3])
    if c1.button("Submit answer", type="primary", use_container_width=True):
        if not answer.strip():
            st.warning("Write or record an answer first, or skip this question.")
        else:
            with st.spinner("Evaluating..."):
                submit(answer)
            st.rerun()
    if c2.button("Skip", use_container_width=True):
        advance()
        st.rerun()

# ------------------------------------------------------------------ report
else:
    if not S.turns:
        hero("No answers recorded", "Start a new session to try again.")
        st.button("Start over", on_click=reset)
        st.stop()

    if S.report is None:
        with st.spinner("Writing your report..."):
            try:
                S.report = final_report(S.profile, S.role, S.turns).model_dump()
            except Exception as e:
                S.report = {"summary": f"The AI summary could not be generated ({e}). "
                                       "Your question-by-question feedback is below.",
                            "strengths": [], "weaknesses": [], "topics_to_revise": [], "practice_plan": []}
        storage.save_session(S.friend, S.role, mean(t["eval"]["score"] for t in S.turns),
                             {"turns": S.turns, "report": S.report})

    avg = mean(t["eval"]["score"] for t in S.turns)
    hist = storage.history(S.friend)
    prev = hist[-2][1] if len(hist) > 1 else None
    words = sum(t["stats"]["words"] for t in S.turns)
    fillers = sum(sum(t["stats"]["fillers"].values()) for t in S.turns)

    top1, top2 = st.columns([4, 1])
    with top1:
        hero("Your interview report", f"{S.friend}  ·  {S.role}")
    top2.download_button("⬇️ Download", report_markdown(), file_name="interview_report.md",
                         mime="text/markdown", use_container_width=True)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Average score", f"{avg:.1f} / 5", delta=f"{avg - prev:+.1f}" if prev is not None else None)
    m2.metric("Answers", len(S.turns))
    m3.metric("Words", words)
    m4.metric("Filler words", fillers)

    tab_sum, tab_q, tab_prog = st.tabs(["📝 Summary", "💬 Question review", "📈 Progress"])
    r = S.report

    with tab_sum:
        st.info(r["summary"])
        a, b = st.columns(2)
        with a:
            st.markdown("#### ✅ Strengths")
            bullets(r["strengths"])
        with b:
            st.markdown("#### ⚠️ Top weaknesses")
            bullets(r["weaknesses"])
        c, d = st.columns(2)
        with c:
            st.markdown("#### 📚 Topics to revise")
            bullets(r["topics_to_revise"])
        with d:
            st.markdown("#### 🗓️ Practice plan")
            bullets(r["practice_plan"])

    with tab_q:
        for i, t in enumerate(S.turns):
            sc = t["eval"]["score"]
            label = f"{score_icon(sc)} {'↳ ' if t['followup'] else ''}{t['question']}  ({sc}/5)"
            with st.expander(label):
                st.markdown(f"**Your answer:** {t['answer'] or '(blank)'}")
                st.markdown(f"**Done well:** {t['eval']['done_well']}")
                st.markdown(f"**Fix:** {t['eval']['to_fix']}")
                if t["eval"].get("sample_answer"):
                    st.markdown(f"**Stronger answer:** {t['eval']['sample_answer']}")
                elif st.button("Write a stronger answer", key=f"rs_{i}"):
                    with st.spinner("Writing..."):
                        t["eval"]["sample_answer"] = make_sample_answer(S.profile, t["question"], [], t["answer"])
                    st.rerun()
                st.caption(f"{t['stats']['words']} words. Filler words: {t['stats']['fillers'] or 'none'}")

    with tab_prog:
        st.markdown("#### Score per answer")
        st.bar_chart({"score": [t["eval"]["score"] for t in S.turns]})
        if len(hist) > 1:
            st.markdown("#### Average score across sessions")
            st.line_chart({"average": [h[1] for h in hist]})
        else:
            st.caption("Do another session to see your progress over time.")