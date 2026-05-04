"""
Resume Parser - Core parsing logic.
Extracts structured data from resumes.
"""

import re
from dataclasses import dataclass, field


@dataclass
class Resume:
    """Structured representation of a parsed resume."""
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
        "summary":    ["summary", "objective", "profile", "about", "about me"],
        "skills":     ["skills", "technical skills", "core competencies",
                       "technologies", "tech stack"],
        "experience": ["experience", "work experience", "employment",
                       "work history", "professional experience"],
        "education":  ["education", "academic background", "qualifications",
                       "educational background"],
        # Sections that appear AFTER education — detected so their content
        # does not bleed into the education bucket
        "other":      ["additional information", "additional", "interests",
                       "hobbies", "certifications", "awards", "achievements",
                       "projects", "volunteer", "references", "declaration",
                       "personal information"],
    }

    def parse(self, text: str) -> Resume:
        """Parse raw resume text into a structured Resume object."""
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

    # ------------------------------------------------------------------
    # Contact extraction
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Section splitting
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Section parsers
    # ------------------------------------------------------------------

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
        Handles multiple education formats seen in real PDFs:

        Format 1 — clean multi-line (TXT/DOCX):
          Bachelor of Science, Computer Science
          Stanford University
          2020

        Format 2 — inline bullet (PDF):
          • Guru Nanak Institute of Technology, Kolkata  July 2019 - June 2023
          • B.Tech in Computer Science

        Format 3 — institution then degree on next line:
          Stanford University
          B.S. Computer Science, 2020

        Format 4 — everything on one line:
          B.Tech, Computer Science - GNIT Kolkata, 2023
        """
        entries = []
        current: dict | None = None

        degree_keywords = [
            "bachelor", "master", "phd", "doctorate", "associate",
            "b.s.", "m.s.", "b.a.", "m.a.", "mba", "b.tech", "m.tech",
            "b.e.", "m.e.", "b.sc", "m.sc", "bs", "ms", "ba", "be",
            "b.com", "m.com", "llb", "mbbs", "diploma",
        ]

        institution_keywords = [
            "university", "college", "institute", "school", "academy",
            "polytechnic", "iit", "nit", "bits", "technology",
        ]

        date_pattern = re.compile(
            r"\b(January|February|March|April|May|June|July|August|September|"
            r"October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
            r"[\s,]+\d{4}"
            r"(?:\s*[-–]\s*"
            r"(?:January|February|March|April|May|June|July|August|September|"
            r"October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
            r"[\s,]+\d{4}|"
            r"\s*[-–]\s*(?:Present|present|Current|current|Now|now))?",
            re.IGNORECASE,
        )

        year_pattern = re.compile(r"\b(19|20)\d{2}\b")

        def strip_bullet(line: str) -> str:
            """Remove leading bullet characters and whitespace."""
            return re.sub(r"^[\s•·\-\*\uf0b7\u2022\u25aa\u2023\u25cf]+\s*", "", line).strip()

        def extract_year(text: str) -> str:
            m = year_pattern.search(text)
            return m.group(0) if m else ""

        def extract_dates(text: str) -> str:
            """Extract full date range string from a line."""
            m = date_pattern.search(text)
            return m.group(0).strip() if m else ""

        def remove_dates(text: str) -> str:
            """Remove date information from a line, leaving institution/degree."""
            cleaned = date_pattern.sub("", text)
            # Clean up leftover punctuation/separators
            cleaned = re.sub(r"[\|\-–,]+\s*$", "", cleaned)
            cleaned = re.sub(r"\s{2,}", " ", cleaned)
            return cleaned.strip()

        def is_degree_line(line: str) -> bool:
            return any(kw in line.lower() for kw in degree_keywords)

        def is_institution_line(line: str) -> bool:
            return any(kw in line.lower() for kw in institution_keywords)

        def parse_inline_entry(line: str) -> dict:
            """
            Parse a single line that contains institution + dates inline.
            e.g. '• Guru Nanak Institute of Technology, Kolkata  July 2019 - June 2023'
            e.g. 'B.S. Computer Science, 2020'
            e.g. 'B.Tech, Computer Science - GNIT Kolkata, 2023'
            """
            dates = extract_dates(line)
            year = extract_year(line)
            content = remove_dates(line)

            # Pattern: "Degree - Institution" or "Degree, Field - Institution"
            if re.search(r"\s[-–]\s", content):
                parts = re.split(r"\s[-–]\s", content, maxsplit=1)
                left, right = parts[0].strip(), parts[1].strip()
                if is_degree_line(left):
                    return {"degree": left, "institution": right, "year": year, "dates": dates}
                if is_institution_line(right):
                    return {"degree": left, "institution": right, "year": year, "dates": dates}

            # Pattern: "Degree, Field" where institution is separate line
            if is_degree_line(content):
                return {"degree": content, "institution": "", "year": year, "dates": dates}

            # Pattern: institution only
            return {"degree": "", "institution": content, "year": year, "dates": dates}

        for line in lines:
            cleaned = strip_bullet(line.strip())
            if not cleaned:
                if current:
                    entries.append(current)
                    current = None
                continue

            has_date = bool(date_pattern.search(cleaned))
            has_degree = is_degree_line(cleaned)
            has_institution = is_institution_line(cleaned)

            # PRE-CHECK: if this is a degree-only line AND the last
            # appended entry has an institution but no degree,
            # retroactively attach the degree to it instead of
            # creating a new entry. This handles the pattern:
            #   bullet 1: "GNIT Kolkata  July 2019"  → institution entry appended
            #   bullet 2: "B.Tech in CSE"            → should attach to bullet 1
            if has_degree and not has_date and not has_institution:
                if entries and entries[-1]["institution"] and not entries[-1]["degree"]:
                    entries[-1]["degree"] = cleaned
                    continue

            # Case 1: line has an institution/degree AND a date inline
            # → self-contained bullet entry e.g.
            # "• GNIT, Kolkata  July 2019 - June 2023"
            if (has_institution or has_degree) and has_date:
                if current:
                    # If previous entry is institution-only with no degree,
                    # this line's date info belongs to it — update and close
                    if current["institution"] and not current["degree"] and not current["year"]:
                        year = extract_year(cleaned)
                        dates = extract_dates(cleaned)
                        if year:
                            current["year"] = year
                        if dates:
                            current["dates"] = dates
                        entries.append(current)
                        current = None
                    else:
                        entries.append(current)
                        current = parse_inline_entry(cleaned)
                        entries.append(current)
                        current = None
                else:
                    current = parse_inline_entry(cleaned)
                    entries.append(current)
                    current = None

            # Case 2: degree line with no date
            elif has_degree and not has_date:
                if current:
                    # Attach degree to existing entry if it has an institution
                    # but no degree yet — this is the consecutive bullet pattern:
                    # "• GNIT, Kolkata  July 2019"  ← institution entry
                    # "• B.Tech in CSE"             ← degree follows
                    if current["institution"] and not current["degree"]:
                        current["degree"] = cleaned
                    else:
                        entries.append(current)
                        current = {"degree": cleaned, "institution": "", "year": "", "dates": ""}
                else:
                    current = {"degree": cleaned, "institution": "", "year": "", "dates": ""}

            # Case 3: institution line with no date
            elif has_institution and not has_date:
                if current:
                    if not current["institution"]:
                        current["institution"] = cleaned
                    else:
                        entries.append(current)
                        current = {"degree": "", "institution": cleaned, "year": "", "dates": ""}
                else:
                    current = {"degree": "", "institution": cleaned, "year": "", "dates": ""}

            # Case 4: year-only line
            elif year_pattern.match(cleaned) and len(cleaned) <= 9:
                if current and not current["year"]:
                    current["year"] = cleaned
                elif current:
                    entries.append(current)
                    current = None

            # Case 5: fallback — skip lines that look like noise
            # (relocation notes, declarations, single short words)
            else:
                if current:
                    if not current["institution"] and not current["degree"]:
                        current["institution"] = cleaned
                    elif current["institution"] and not current["degree"]:
                        current["degree"] = cleaned
                    # else: ignore — don't append noise to a complete entry

        if current:
            entries.append(current)

        # Clean up:
        # 1. Remove entries with no useful info
        # 2. Remove entries where institution looks like noise
        #    (short lines, relocation notes, declarations)
        noise_patterns = re.compile(
            r"(relocation|hybrid|remote|opportunity|open to|declaration|"
            r"hereby|certify|information is true)",
            re.IGNORECASE
        )
        entries = [
            e for e in entries
            if (e.get("degree") or e.get("institution"))
            and not noise_patterns.search(e.get("institution", ""))
            and not noise_patterns.search(e.get("degree", ""))
            and len(e.get("institution", "") + e.get("degree", "")) > 5
        ]

        return entries
