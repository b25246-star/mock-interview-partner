from pydantic import BaseModel, Field


class Project(BaseModel):
    name: str
    tech: list[str] = []
    description: str = ""


class Profile(BaseModel):
    name: str = ""
    education: str = ""
    skills: list[str] = []
    projects: list[Project] = []
    internships: list[str] = []
    achievements: list[str] = []


class Question(BaseModel):
    type: str  # intro | resume | technical | behavioral | hr
    difficulty: str  # easy | medium | hard
    question: str
    good_answer_includes: list[str] = []


class Plan(BaseModel):
    questions: list[Question]


class FollowUp(BaseModel):
    needs_followup: bool
    followup_question: str = ""
    reason: str = ""


class Evaluation(BaseModel):
    score: int = Field(ge=1, le=5)
    done_well: str
    to_fix: str
    sample_answer: str = ""


class SampleAnswer(BaseModel):
    sample_answer: str


class Report(BaseModel):
    summary: str
    strengths: list[str]
    weaknesses: list[str]
    topics_to_revise: list[str]
    practice_plan: list[str]