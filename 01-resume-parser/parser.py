"""
Resume Parser - Core parsing logic.
Extracts structured data from plain text resumes.
"""

import re
from dataclasses import dataclass, field


@dataclass
class Resume:
    # Structured representation of a parsed resume.
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    summary: str = ""
    skills: list[str] = field(default_factory=list)
    experience: list[dict] = field(default_factory=list)
    education: list[dict] = field(default_factory=list)
    raw_text: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "location": self.location,
            "summary": self.summary,
            "skills": self.skills,
            "experience": self.experience,
            "education": self.education,
        }


class ResumeParser:
    """
    Parses plain text resumes into structured Resume objects.

    Uses regex patterns and section detection to extract:
    - Contact info (name, email, phone, location)
    - Skills
    - Work experience
    - Education
    """

    # --- Regex Patterns ---
    EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
    PHONE_PATTERN = re.compile(r"(\+?1?\s?)?(\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4})")
    LOCATION_PATTERN = re.compile(
        r"\b([A-Z][a-zA-Z\s]+,\s?[A-Z]{2})\b"  # City, ST format
    )

    # Section headers we look for (case-insensitive)
    SECTION_HEADERS = {
        "summary": ["summary", "objective", "profile", "about"],
        "skills": ["skills", "technical skills", "core competencies", "technologies"],
        "experience": ["experience", "work experience", "employment", "work history"],
        "education": ["education", "academic background", "qualifications"],
    }

    def parse(self, text: str) -> Resume:
        # Parse raw resume text into a structured Resume object.
        resume = Resume(raw_text=text)
        lines = [line.strip() for line in text.strip().splitlines()]
        non_empty = [l for l in lines if l]

        resume.name = self._extract_name(non_empty)
        resume.email = self._extract_email(text)
        resume.phone = self._extract_phone(text)
        resume.location = self._extract_location(text)

        sections = self._split_into_sections(lines)

        resume.summary = self._parse_summary(sections.get("summary", []))
        resume.skills = self._parse_skills(sections.get("skills", []))
        resume.experience = self._parse_experience(sections.get("experience", []))
        resume.education = self._parse_education(sections.get("education", []))

        return resume

    # Contact extraction

    def _extract_name(self, lines: list[str]) -> str:
        """
        Heuristic: the name is usually the first non-empty line,
        contains only letters/spaces, and has no digits or @ signs.
        """
        for line in lines[:5]:
            if (
                line
                and not self.EMAIL_PATTERN.search(line)
                and not self.PHONE_PATTERN.search(line)
                and not any(char.isdigit() for char in line)
                and len(line.split()) <= 5
            ):
                return line
        return ""

    def _extract_email(self, text: str) -> str:
        match = self.EMAIL_PATTERN.search(text)
        return match.group(0) if match else ""

    def _extract_phone(self, text: str) -> str:
        match = self.PHONE_PATTERN.search(text)
        return match.group(0).strip() if match else ""

    def _extract_location(self, text: str) -> str:
        match = self.LOCATION_PATTERN.search(text)
        return match.group(0).strip() if match else ""


    # Section splitting


    def _is_section_header(self, line: str) -> str | None:
        """
        Returns the canonical section name if the line is a section header,
        otherwise returns None.
        """
        clean = line.lower().strip(" :-_")
        for section, keywords in self.SECTION_HEADERS.items():
            if clean in keywords:
                return section
        return None

    def _split_into_sections(self, lines: list[str]) -> dict[str, list[str]]:
        """
        Walk through lines and group them under their section headers.
        Lines before any header go into an 'header' bucket (contact info).
        """
        sections: dict[str, list[str]] = {}
        current_section = "header"

        for line in lines:
            detected = self._is_section_header(line)
            if detected:
                current_section = detected
                sections.setdefault(current_section, [])
            else:
                sections.setdefault(current_section, []).append(line)

        return sections

    # Section parsers

    def _parse_summary(self, lines: list[str]) -> str:
        return " ".join(l for l in lines if l).strip()

    def _parse_skills(self, lines: list[str]) -> list[str]:
        """
        Skills may be comma-separated on one line, or one per line,
        or separated by pipes/bullets. Handle all cases.
        """
        skills = []
        for line in lines:
            if not line:
                continue
            # Split on common delimiters
            parts = re.split(r"[,|•·\-]\s*", line)
            for part in parts:
                cleaned = part.strip().strip("•·-").strip()
                if cleaned and len(cleaned) > 1:
                    skills.append(cleaned)
        return list(dict.fromkeys(skills))  # deduplicate, preserve order

    def _parse_experience(self, lines: list[str]) -> list[dict]:
        """
        Experience entries typically look like:
          Job Title - Company Name
          Month Year – Month Year (or Present)
          • bullet point description
        """
        entries = []
        current: dict | None = None
        date_pattern = re.compile(
            r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|"
            r"March|April|June|July|August|September|October|November|December)"
            r"[\s,]+\d{4}",
            re.IGNORECASE,
        )

        for line in lines:
            if not line:
                if current:
                    entries.append(current)
                    current = None
                continue

            # Line with a date range → start of a new entry
            if date_pattern.search(line):
                if current:
                    entries.append(current)
                current = {"dates": line, "title": "", "company": "", "bullets": []}

            elif current is None:
                # First non-empty line before any date = title/company line
                if " at " in line.lower():
                    parts = re.split(r"\s+at\s+", line, flags=re.IGNORECASE)
                    current = {
                        "dates": "",
                        "title": parts[0].strip(),
                        "company": parts[1].strip() if len(parts) > 1 else "",
                        "bullets": [],
                    }
                elif " - " in line or " – " in line:
                    parts = re.split(r"\s[-–]\s", line, maxsplit=1)
                    current = {
                        "dates": "",
                        "title": parts[0].strip(),
                        "company": parts[1].strip() if len(parts) > 1 else "",
                        "bullets": [],
                    }
                else:
                    current = {"dates": "", "title": line, "company": "", "bullets": []}

            else:
                # Bullet point or description line
                bullet = line.lstrip("•·-– ").strip()
                if bullet:
                    current["bullets"].append(bullet)

        if current:
            entries.append(current)

        return entries

    def _parse_education(self, lines: list[str]) -> list[dict]:
        """
        Education entries typically look like:
          Degree, Field of Study
          University Name
          Year
        """
        entries = []
        current: dict | None = None

        degree_keywords = ["bachelor", "master", "phd", "doctorate", "associate",
                           "b.s.", "m.s.", "b.a.", "m.a.", "mba", "bs", "ms", "ba"]

        for line in lines:
            if not line:
                if current:
                    entries.append(current)
                    current = None
                continue

            line_lower = line.lower()
            if any(kw in line_lower for kw in degree_keywords):
                if current:
                    entries.append(current)
                current = {"degree": line, "institution": "", "year": ""}
            elif current:
                # Check if this looks like a year
                year_match = re.search(r"\b(19|20)\d{2}\b", line)
                if year_match and not current["year"]:
                    current["year"] = year_match.group(0)
                elif not current["institution"]:
                    current["institution"] = line
            else:
                current = {"degree": "", "institution": line, "year": ""}

        if current:
            entries.append(current)

        return entries
