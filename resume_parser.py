import pdfplumber

from llm import chat_json, load_prompt
from models import Profile


def extract_text(file) -> str:
    """file is a Streamlit UploadedFile (pdf or txt)."""
    name = file.name.lower()
    if name.endswith(".pdf"):
        with pdfplumber.open(file) as pdf:
            return "\n".join((page.extract_text() or "") for page in pdf.pages).strip()
    return file.read().decode("utf-8", errors="ignore").strip()


def parse_profile(resume_text: str) -> Profile:
    if len(resume_text) < 50:
        raise ValueError("Could not read enough text from the resume. Is it a scanned image?")
    return chat_json(load_prompt("profile.txt"), f"RESUME TEXT:\n{resume_text[:8000]}", Profile)