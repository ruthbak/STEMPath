from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


# Keep this aligned with the skills your current system can actually teach/pathfind.
INTERNAL_SKILL_KEYWORDS: dict[str, list[str]] = {
    "Python": ["python", "jupyter", "anaconda"],
    "SQL": ["sql", "mysql", "postgresql", "postgres", "sqlite", "oracle database", "transact-sql"],
    "JavaScript": ["javascript", "node.js", "nodejs", "react", "angular", "vue", "typescript"],
    "Java": ["java", "spring"],
    "HTML": ["html", "html5"],
    "CSS": ["css", "css3", "sass", "bootstrap"],
    "Git": ["git", "github", "gitlab", "bitbucket", "version control"],
    "Data Visualization": ["tableau", "power bi", "matplotlib", "seaborn", "plotly", "dashboard", "visualization"],
    "Machine Learning": ["machine learning", "tensorflow", "pytorch", "scikit-learn", "scikit learn", "keras"],
    "Networking": ["network", "tcp/ip", "cisco", "router", "switch", "lan", "wan"],
    "Linux": ["linux", "unix", "bash", "shell"],
    "Security Basics": ["cybersecurity", "information security", "splunk", "siem", "firewall", "ids", "ips"],
    "Cloud": ["aws", "amazon web services", "azure", "gcp", "google cloud", "docker", "kubernetes", "cloud"],
    "APIs": ["api", "apis", "rest", "graphql", "postman", "microservices"],
    "Statistics": ["statistics", "statistical", "spss", "sas", "rstudio"],
    "Excel": ["excel", "microsoft excel", "spreadsheet"],
    "Research": ["matlab", "labview", "research"],
}

ALLOWED_SOC_PREFIXES = {"15", "17", "19"}  # add "29" later if you want health STEM
DEFAULT_TOP_SKILLS = 6
MIN_MAPPED_SKILLS = 3


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        return list(reader)


def soc_prefix(onet_code: str) -> str:
    return onet_code.split("-")[0].strip()


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def infer_category(prefix: str, title: str) -> str:
    t = title.lower()

    if prefix == "15":
        if any(x in t for x in ["data", "statistician", "bi analyst", "business intelligence", "database"]):
            return "Data"
        if any(x in t for x in ["security", "cyber", "information assurance"]):
            return "Security"
        return "Software"

    if prefix == "17":
        return "Engineering"

    if prefix == "19":
        return "Science"

    if prefix == "29":
        return "Healthcare"

    return "STEM"


def contains_keyword(text: str, keyword: str) -> bool:
    text = text.lower()
    keyword = keyword.lower()

    # safer whole-word matching for short tokens
    if len(keyword) <= 3 or keyword in {"api", "sql", "css", "aws", "gcp"}:
        pattern = r"\b" + re.escape(keyword) + r"\b"
        return re.search(pattern, text) is not None

    return keyword in text


def map_tech_example_to_internal_skills(example: str, commodity_title: str = "") -> set[str]:
    text = f"{example} {commodity_title}".lower()
    matched: set[str] = set()

    for internal_skill, keywords in INTERNAL_SKILL_KEYWORDS.items():
        for kw in keywords:
            if contains_keyword(text, kw):
                matched.add(internal_skill)
                break

    return matched


def load_occupations(path: Path) -> dict[str, dict]:
    rows = read_tsv(path)
    occupations: dict[str, dict] = {}

    for row in rows:
        code = row.get("O*NET-SOC Code", "").strip()
        title = row.get("Title", "").strip()
        description = row.get("Description", "").strip()

        if not code or not title:
            continue

        occupations[code] = {
            "code": code,
            "title": title,
            "description": description,
        }

    return occupations


def load_job_zones(path: Path) -> dict[str, int]:
    rows = read_tsv(path)
    zones: dict[str, int] = {}

    for row in rows:
        code = row.get("O*NET-SOC Code", "").strip()
        raw_zone = row.get("Job Zone", "").strip()
        if not code or not raw_zone:
            continue

        try:
            zones[code] = int(raw_zone)
        except ValueError:
            continue

    return zones


def load_technology_skill_scores(path: Path) -> tuple[dict[str, Counter], dict[str, list[str]]]:
    """
    Returns:
      - score counter per occupation for internal skills
      - sample raw technology examples per occupation
    """
    rows = read_tsv(path)
    scores_by_occ: dict[str, Counter] = defaultdict(Counter)
    examples_by_occ: dict[str, list[str]] = defaultdict(list)

    for row in rows:
        code = row.get("O*NET-SOC Code", "").strip()
        example = row.get("Example", "").strip()
        commodity_title = row.get("Commodity Title", "").strip()
        hot = row.get("Hot Technology", "").strip().upper()
        in_demand = row.get("In Demand", "").strip().upper()

        if not code or not example:
            continue

        mapped_skills = map_tech_example_to_internal_skills(example, commodity_title)
        if not mapped_skills:
            continue

        base_score = 1
        if hot == "Y":
            base_score += 2
        if in_demand == "Y":
            base_score += 3

        for skill in mapped_skills:
            scores_by_occ[code][skill] += base_score

        if example not in examples_by_occ[code]:
            examples_by_occ[code].append(example)

    return scores_by_occ, examples_by_occ


def build_roles_json(
    occupations_path: Path,
    tech_skills_path: Path,
    job_zones_path: Path,
    output_path: Path,
    allowed_prefixes: set[str],
    min_mapped_skills: int,
    top_n_skills: int,
) -> None:
    occupations = load_occupations(occupations_path)
    job_zones = load_job_zones(job_zones_path)
    tech_scores_by_occ, raw_examples_by_occ = load_technology_skill_scores(tech_skills_path)

    roles: list[dict] = []

    for code, occ in occupations.items():
        prefix = soc_prefix(code)
        if prefix not in allowed_prefixes:
            continue

        # joining with job zones removes many non-data-level/title-only rows
        if code not in job_zones:
            continue

        skill_counter = tech_scores_by_occ.get(code, Counter())
        top_skills = [skill for skill, _score in skill_counter.most_common(top_n_skills)]

        # Skip occupations that do not map well to your current internal skill graph
        if len(top_skills) < min_mapped_skills:
            continue

        title = occ["title"]
        description = occ["description"]

        role = {
            "id": slugify(title),
            "title": title,
            "category": infer_category(prefix, title),
            "description": description,
            "top_skills": top_skills,
            "onet_code": code,
            "job_zone": job_zones[code],
            "onet_tech_examples": raw_examples_by_occ.get(code, [])[:10],
        }
        roles.append(role)

    roles.sort(key=lambda r: (r["category"], r["title"]))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(roles, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(roles)} roles to {output_path}")
    categories = Counter(role["category"] for role in roles)
    print("Category counts:", dict(categories))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate STEMPath roles.json from O*NET raw files.")
    parser.add_argument("--occupations", required=True, help="Path to Occupation Data.txt")
    parser.add_argument("--tech-skills", required=True, help="Path to Technology Skills.txt")
    parser.add_argument("--job-zones", required=True, help="Path to Job Zones.txt")
    parser.add_argument("--output", default="data/roles.json", help="Output roles.json path")
    parser.add_argument("--soc", nargs="+", default=["15", "17", "19"], help="SOC major-group prefixes")
    parser.add_argument("--min-skills", type=int, default=MIN_MAPPED_SKILLS, help="Minimum mapped skills to keep a role")
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_SKILLS, help="Top N mapped skills per role")
    args = parser.parse_args()

    build_roles_json(
        occupations_path=Path(args.occupations),
        tech_skills_path=Path(args.tech_skills),
        job_zones_path=Path(args.job_zones),
        output_path=Path(args.output),
        allowed_prefixes=set(args.soc),
        min_mapped_skills=args.min_skills,
        top_n_skills=args.top_n,
    )


if __name__ == "__main__":
    main()