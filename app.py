from statistics import mean

import streamlit as st

import storage
from evaluator import evaluate_answer, filler_stats, final_report
from interviewer import PERSONAS, decide_followup
from planner import build_plan
from resume_parser import extract_text, parse_profile

st.set_page_config(page_title="Mock Interview Partner", page_icon="🎤")
storage.init()
S = st.session_state

DEFAULTS = {
    "stage": "setup", "profile": None, "plan": [], "qi": 0, "fu_used": 0,
    "current": None, "turns": [], "last": None, "report": None,
    "friend": "", "role": "", "persona": "",
}
for k, v in DEFAULTS.items():
    S.setdefault(k, v)


def q_to_state(q: dict, followup: bool = False) -> dict:
    return {"text": q["question"], "type": q["type"], "good": q["good_answer_includes"], "followup": followup}


def submit(answer: str):
    cur = S.current
    ev = evaluate_answer(S.profile, cur["text"], cur["good"], answer)
    S.turns.append({
        "question": cur["text"], "type": cur["type"], "followup": cur["followup"],
        "answer": answer, "eval": ev.model_dump(), "stats": filler_stats(answer),
    })
    S.last = ev.model_dump()

    if S.fu_used < 2 and answer.strip():
        fu = decide_followup(cur["text"], answer, S.persona)
        if fu.needs_followup and fu.followup_question.strip():
            S.fu_used += 1
            S.current = {**cur, "text": fu.followup_question.strip(), "followup": True}
            return

    S.qi += 1
    S.fu_used = 0
    if S.qi >= len(S.plan):
        S.stage = "report"
    else:
        S.current = q_to_state(S.plan[S.qi])


def reset():
    for k, v in DEFAULTS.items():
        S[k] = v


# ---------------------------------------------------------------- setup
if S.stage == "setup":
    st.title("🎤 Mock Interview Partner")
    st.caption("Runs on a local open-source model. Your resume never leaves this laptop.")

    friend = st.text_input("Your name")
    role = st.text_input("Target role", placeholder="e.g. Software Developer, Data Analyst")
    jd = st.text_area("Job description (optional)", height=100)
    persona_name = st.selectbox("Interviewer persona", list(PERSONAS))
    n = st.slider("Number of main questions", 5, 10, 8)
    resume = st.file_uploader("Resume (PDF or TXT)", type=["pdf", "txt"])

    if st.button("Start interview", type="primary", disabled=not (friend and role and resume)):
        try:
            with st.spinner("Reading your resume and planning questions..."):
                profile = parse_profile(extract_text(resume))
                plan = build_plan(profile, role, jd, PERSONAS[persona_name], n, storage.past_questions(friend))
        except Exception as e:
            st.error(f"Something went wrong: {e}\n\nIs Ollama running and the model pulled?")
            st.stop()
        S.update(
            profile=profile, plan=[q.model_dump() for q in plan], friend=friend, role=role,
            persona=PERSONAS[persona_name], qi=0, fu_used=0, turns=[], last=None,
            current=q_to_state(plan[0].model_dump()), stage="interview",
        )
        st.rerun()

# ---------------------------------------------------------------- interview
elif S.stage == "interview":
    st.title("Interview in progress")
    st.progress(S.qi / len(S.plan), text=f"Question {S.qi + 1} of {len(S.plan)}")

    if S.last:
        with st.expander(f"Feedback on your last answer: {S.last['score']}/5", expanded=True):
            st.markdown(f"**Done well:** {S.last['done_well']}")
            st.markdown(f"**Fix:** {S.last['to_fix']}")
            with st.popover("Show a stronger sample answer"):
                st.write(S.last["sample_answer"])

    cur = S.current
    st.subheader(("Follow-up: " if cur["followup"] else "") + cur["text"])

    key = f"ans_{len(S.turns)}"

    # Optional voice input (needs faster-whisper and Streamlit with st.audio_input)
    if hasattr(st, "audio_input"):
        audio = st.audio_input("Or record your answer", key=f"aud_{len(S.turns)}")
        if audio and st.button("Use recording"):
            try:
                from voice import transcribe
                with st.spinner("Transcribing..."):
                    S[key] = transcribe(audio.getvalue())
            except ImportError:
                st.warning("Install faster-whisper to use voice answers.")

    answer = st.text_area("Your answer", key=key, height=180)
    col1, col2 = st.columns(2)
    if col1.button("Submit answer", type="primary"):
        with st.spinner("Evaluating..."):
            submit(answer)
        st.rerun()
    if col2.button("End interview now"):
        S.stage = "report"
        st.rerun()

# ---------------------------------------------------------------- report
else:
    st.title("📋 Your interview report")
    if not S.turns:
        st.info("No answers recorded.")
        st.button("Start over", on_click=reset)
        st.stop()

    if S.report is None:
        with st.spinner("Writing your report..."):
            S.report = final_report(S.profile, S.role, S.turns).model_dump()
        avg_now = mean(t["eval"]["score"] for t in S.turns)
        storage.save_session(S.friend, S.role, avg_now, {"turns": S.turns, "report": S.report})

    avg = mean(t["eval"]["score"] for t in S.turns)
    hist = storage.history(S.friend)
    c1, c2 = st.columns(2)
    c1.metric("Average score", f"{avg:.1f} / 5")
    if len(hist) > 1:
        c2.metric("Change vs previous session", f"{avg - hist[-2][1]:+.1f}")

    r = S.report
    st.write(r["summary"])
    for title, items in [("Strengths", r["strengths"]), ("Top weaknesses", r["weaknesses"]),
                         ("Topics to revise", r["topics_to_revise"]), ("Practice plan", r["practice_plan"])]:
        st.subheader(title)
        for i in items:
            st.markdown(f"- {i}")

    if len(hist) > 1:
        st.subheader("Progress across sessions")
        st.line_chart({"avg score": [h[1] for h in hist]})

    st.subheader("Question by question")
    for t in S.turns:
        label = f"{'↳ ' if t['followup'] else ''}{t['question']}  ({t['eval']['score']}/5)"
        with st.expander(label):
            st.markdown(f"**Your answer:** {t['answer'] or '(blank)'}")
            st.markdown(f"**Done well:** {t['eval']['done_well']}")
            st.markdown(f"**Fix:** {t['eval']['to_fix']}")
            st.markdown(f"**Stronger answer:** {t['eval']['sample_answer']}")
            st.caption(f"{t['stats']['words']} words. Filler words: {t['stats']['fillers'] or 'none'}")

    st.button("Start a new session", on_click=reset)