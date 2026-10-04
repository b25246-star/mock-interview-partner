# Mock Interview Partner

A free, private mock interviewer for placement season. Upload a resume, pick a role, and get tailored questions, follow-ups, strict per-answer feedback, and a final report. Everything runs locally with an open-weight model via Ollama.

## Setup

1. Install [Ollama](https://ollama.com) and pull a model:
   ```
   ollama pull qwen2.5:7b
   ```
   (On a weak laptop use `llama3.2:3b` and set `MODEL=llama3.2:3b`.)
2. Create a virtual environment and install dependencies:
   ```
   python -m venv venv
   venv\Scripts\activate        # Windows
   source venv/bin/activate     # macOS / Linux
   pip install -r requirements.txt
   ```
3. Run:
   ```
   streamlit run app.py
   ```

Try it with `samples/sample_resume.txt`.

## Customize

- `prompts/personas/*.txt`: add a file to add an interviewer persona
- `rubric.yaml`: change the scoring criteria and anchors
- `prompts/*.txt`: change how questions, follow-ups, and feedback behave

## Optional voice answers

`pip install faster-whisper`, then use the record button in the interview screen.