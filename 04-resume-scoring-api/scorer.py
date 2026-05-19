"""
Scorer

Core resume scoring logic.
Compares a resume against a job description using keyword matching.

Scoring breakdown:
- Skills match     : 60% weight
- Experience match : 25% weight
- Education match  : 15% weight
"""

import re
from dataclasses import dataclass, field


# ------------------------------------------------------------------
# Keyword banks by category
# ------------------------------------------------------------------

SKILL_PATTERNS = [
    # Languages
    "python", "javascript", "typescript", "java", "go", "golang", "rust",
    "c++", "c#", "ruby", "php", "swift", "kotlin", "scala", "r",

    # Frameworks / Libraries
    "fastapi", "django", "flask", "react", "vue", "angular", "nextjs",
    "express", "spring", "rails", "laravel", "sqlalchemy", "pydantic",

    # Databases
    "postgresql", "postgres", "mysql", "sqlite", "mongodb", "redis",
    "elasticsearch", "cassandra", "dynamodb", "snowflake", "bigquery",

    # Cloud / DevOps
    "aws", "gcp", "azure", "docker", "kubernetes", "k8s", "terraform",
    "ci/cd", "github actions", "jenkins", "ansible",

    # AI / ML
    "machine learning", "deep learning", "nlp", "llm", "rag",
    "langchain", "openai", "pytorch", "tensorflow", "scikit-learn",
    "pandas", "numpy", "huggingface",

    # Tools / Concepts
    "git", "rest", "graphql", "grpc", "microservices", "kafka",
    "celery", "airflow", "spark", "linux", "bash", "sql",
]

EXPERIENCE_KEYWORDS = [
    "years of experience", "year experience", "years experience",
    "led", "managed", "built", "designed", "architected", "developed",
    "deployed", "scaled", "optimized", "mentored", "collaborated",
]

EDUCATION_KEYWORDS = [
    "bachelor", "master", "phd", "b.s.", "m.s.", "b.tech", "m.tech",
    "b.e.", "computer science", "software engineering", "information technology",
    "data science", "electrical engineering",
]


# ------------------------------------------------------------------
# Data structures
# ------------------------------------------------------------------

@dataclass
class ScoreResult:
    score: float
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    recommendation: str = ""
    resume_snippet: str = ""


# ------------------------------------------------------------------
# Scorer
# ------------------------------------------------------------------

class ResumeScorer:
    """
    Scores a resume against a job description.

    Weights:
        skills_weight      = 0.60
        experience_weight  = 0.25
        education_weight   = 0.15
    """

    SKILLS_WEIGHT     = 0.60
    EXPERIENCE_WEIGHT = 0.25
    EDUCATION_WEIGHT  = 0.15

    def score(self, resume_text: str, job_description: str) -> ScoreResult:
        """Main entry point. Returns a ScoreResult with full breakdown."""
        resume_lower = resume_text.lower()
        jd_lower     = job_description.lower()

        # Extract keywords from JD
        jd_skills     = self._extract_skills(jd_lower)
        jd_experience = self._extract_experience_signals(jd_lower)
        jd_education  = self._extract_education_signals(jd_lower)

        # Match against resume
        matched, missing = self._match_skills(resume_lower, jd_skills)
        exp_score  = self._score_experience(resume_lower, jd_experience)
        edu_score  = self._score_education(resume_lower, jd_education)

        # Skill score = % of JD skills found in resume
        skill_score = (len(matched) / len(jd_skills) * 100) if jd_skills else 50.0

        # Weighted final score
        final = (
            skill_score * self.SKILLS_WEIGHT +
            exp_score   * self.EXPERIENCE_WEIGHT +
            edu_score   * self.EDUCATION_WEIGHT
        )
        final = round(min(max(final, 0), 100), 2)

        return ScoreResult(
            score=final,
            matched_skills=matched,
            missing_skills=missing,
            recommendation=self._recommend(final),
            resume_snippet=self._snippet(resume_text),
        )

    # ------------------------------------------------------------------
    # Extraction helpers
    # ------------------------------------------------------------------

    def _extract_skills(self, text: str) -> list[str]:
        """Find which skills from our bank appear in the text."""
        found = []
        for skill in SKILL_PATTERNS:
            # Use word boundaries to avoid partial matches
            pattern = r"\b" + re.escape(skill) + r"\b"
            if re.search(pattern, text):
                found.append(skill)
        return found

    def _extract_experience_signals(self, text: str) -> list[str]:
        return [kw for kw in EXPERIENCE_KEYWORDS if kw in text]

    def _extract_education_signals(self, text: str) -> list[str]:
        return [kw for kw in EDUCATION_KEYWORDS if kw in text]

    # ------------------------------------------------------------------
    # Matching helpers
    # ------------------------------------------------------------------

    def _match_skills(
        self, resume: str, jd_skills: list[str]
    ) -> tuple[list[str], list[str]]:
        """Split JD skills into matched (in resume) and missing."""
        matched = []
        missing = []
        for skill in jd_skills:
            pattern = r"\b" + re.escape(skill) + r"\b"
            if re.search(pattern, resume):
                matched.append(skill)
            else:
                missing.append(skill)
        return matched, missing

    def _score_experience(self, resume: str, jd_signals: list[str]) -> float:
        """
        Score experience match as % of JD experience signals found in resume.
        Also checks for year mentions (e.g. '5 years').
        """
        if not jd_signals:
            return 70.0  # neutral if JD has no experience requirements

        hits = sum(1 for kw in jd_signals if kw in resume)
        base = (hits / len(jd_signals)) * 100

        # Bonus: resume mentions years of experience
        if re.search(r"\d+\+?\s+years?", resume):
            base = min(base + 10, 100)

        return round(base, 2)

    def _score_education(self, resume: str, jd_signals: list[str]) -> float:
        """Score education match."""
        if not jd_signals:
            return 70.0  # neutral if JD has no education requirements

        hits = sum(1 for kw in jd_signals if kw in resume)
        return round((hits / len(jd_signals)) * 100, 2)

    # ------------------------------------------------------------------
    # Output helpers
    # ------------------------------------------------------------------

    def _recommend(self, score: float) -> str:
        if score >= 80:
            return "Strong match — recommend for interview"
        elif score >= 60:
            return "Good match — consider for interview"
        elif score >= 40:
            return "Partial match — review manually"
        else:
            return "Weak match — likely not suitable"

    def _snippet(self, resume_text: str, max_chars: int = 300) -> str:
        """Return the first 300 chars of the resume as a preview."""
        snippet = resume_text.strip()[:max_chars]
        if len(resume_text) > max_chars:
            snippet += "..."
        return snippet
