"""Optional voice answers. Needs: pip install faster-whisper"""
from functools import lru_cache
from io import BytesIO


@lru_cache(maxsize=1)
def _model():
    from faster_whisper import WhisperModel

    return WhisperModel("small", compute_type="int8")  # CPU friendly


def transcribe(audio_bytes: bytes) -> str:
    segments, _ = _model().transcribe(BytesIO(audio_bytes), vad_filter=True)
    return " ".join(s.text.strip() for s in segments).strip()