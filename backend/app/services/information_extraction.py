"""Rule-based skill/education/experience extraction. spaCy NER is optional."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

TAXONOMY_PATH = Path(__file__).with_name("skill_taxonomy.json")

EDUCATION_PATTERNS = [
    (re.compile(r"\bB\.?\s*C\.?\s*A\.?\b", re.I), "BCA"),
    (re.compile(r"\bBachelor of Computer Applications\b", re.I), "BCA"),
    (re.compile(r"\bB\.?\s*Sc\.?\b", re.I), "B.Sc"),
    (re.compile(r"\bBachelor of Science\b", re.I), "B.Sc"),
    (re.compile(r"\bB\.?\s*Tech\.?\b", re.I), "B.Tech"),
    (re.compile(r"\bBachelor of Technology\b", re.I), "B.Tech"),
    (re.compile(r"\bM\.?\s*C\.?\s*A\.?\b", re.I), "MCA"),
    (re.compile(r"\bMaster of Computer Applications\b", re.I), "MCA"),
    (re.compile(r"\bM\.?\s*Sc\.?\b", re.I), "M.Sc"),
    (re.compile(r"\bMaster of Science\b", re.I), "M.Sc"),
    (re.compile(r"\bM\.?\s*Tech\.?\b", re.I), "M.Tech"),
    (re.compile(r"\bMaster of Technology\b", re.I), "M.Tech"),
    (re.compile(r"\bbachelor'?s\b", re.I), "Bachelor's"),
    (re.compile(r"\bmaster'?s\b", re.I), "Master's"),
]

EXPERIENCE_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:experience|exp)\b",
    re.I,
)
EXPERIENCE_RE_ALT = re.compile(
    r"(?:experience|exp)\s*(?:of|:)?\s*(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\b",
    re.I,
)

# Isolated "C" as a programming language is too noisy; C++ / C# are listed instead.
SKIP_ALIASES = {"c", "py", "js", "ts", "ml", "dl", "cv", "tf"}


@lru_cache(maxsize=1)
def load_taxonomy() -> list[dict]:
    data = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
    entries = []
    for item in data.get("skills", []):
        canonical = item["canonical"]
        aliases = []
        for alias in item.get("aliases", []):
            alias_n = alias.strip().lower()
            if alias_n and alias_n not in SKIP_ALIASES:
                aliases.append(alias_n)
        aliases.sort(key=len, reverse=True)
        entries.append({"canonical": canonical, "aliases": aliases})
    return entries


def _phrase_pattern(alias: str) -> re.Pattern:
    escaped = re.escape(alias)
    escaped = escaped.replace(r"\ ", r"[\s/]+")
    escaped = escaped.replace(r"\+\+", r"\+\+")
    return re.compile(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", re.I)


@lru_cache(maxsize=1)
def _compiled_skills() -> list[tuple[str, str, re.Pattern]]:
    compiled = []
    for entry in load_taxonomy():
        for alias in entry["aliases"]:
            compiled.append((entry["canonical"], alias, _phrase_pattern(alias)))
    compiled.sort(key=lambda row: len(row[1]), reverse=True)
    return compiled


def _snippet(text: str, start: int, end: int, radius: int = 70) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    fragment = text[left:right].replace("\n", " ").strip()
    if left > 0:
        fragment = "…" + fragment
    if right < len(text):
        fragment = fragment + "…"
    return fragment[:180]


def extract_skills(text: str) -> list[dict]:
    found: dict[str, dict] = {}
    for canonical, _alias, pattern in _compiled_skills():
        if canonical in found:
            continue
        match = pattern.search(text)
        if match:
            found[canonical] = {
                "name": canonical,
                "evidence": _snippet(text, match.start(), match.end()),
            }
    return list(found.values())


def extract_education(text: str) -> list[dict]:
    found: dict[str, dict] = {}
    for pattern, name in EDUCATION_PATTERNS:
        match = pattern.search(text)
        if match and name not in found:
            found[name] = {"name": name, "evidence": _snippet(text, match.start(), match.end())}
    return list(found.values())


def extract_experience(text: str) -> tuple[float | None, str | None]:
    match = EXPERIENCE_RE.search(text) or EXPERIENCE_RE_ALT.search(text)
    if not match:
        return None, None
    years = float(match.group(1))
    return years, _snippet(text, match.start(), match.end())


def ner_is_available() -> bool:
    try:
        import spacy  # noqa: F401
        from spacy.util import is_package

        return bool(is_package("en_core_web_sm"))
    except Exception:
        return False


def extract_organizations(text: str) -> tuple[list[str], bool]:
    if not ner_is_available():
        return [], False
    try:
        import spacy

        nlp = spacy.load("en_core_web_sm", disable=["tagger", "parser", "lemmatizer"])
        doc = nlp(text[:8000])
        orgs = []
        seen = set()
        for ent in doc.ents:
            if ent.label_ == "ORG":
                name = ent.text.strip()
                key = name.lower()
                if name and key not in seen:
                    seen.add(key)
                    orgs.append(name)
        return orgs[:20], True
    except Exception:
        return [], False


def extract_information(text: str) -> dict:
    skills = extract_skills(text)
    education = extract_education(text)
    years, evidence = extract_experience(text)
    orgs, ner_ok = extract_organizations(text)
    return {
        "skills": skills,
        "education": education,
        "stated_experience_years": years,
        "experience_evidence": evidence,
        "organizations": orgs,
        "ner_available": ner_ok,
    }


def canonical_skill_names(names: list[str]) -> list[str]:
    mapping = {}
    for entry in load_taxonomy():
        mapping[entry["canonical"].lower()] = entry["canonical"]
        for alias in entry["aliases"]:
            mapping[alias.lower()] = entry["canonical"]
    result = []
    seen = set()
    for name in names:
        if not name:
            continue
        canonical = mapping.get(name.strip().lower(), name.strip())
        key = canonical.lower()
        if key not in seen:
            seen.add(key)
            result.append(canonical)
    return result
