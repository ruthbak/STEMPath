from flask import Flask, render_template, request, redirect, url_for, session
import os
import re
import pdfplumber
from docx import Document
import json
from pathlib import Path

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-me"  # required for session


# -----------------------------
# Roles Catalog (using JSON)
# -----------------------------
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
ROLES_PATH = DATA_DIR / "roles.json"


def load_roles():
    """
    Loads roles from data/roles.json.
    Called inside routes so updates show without editing code.
    """
    if not ROLES_PATH.exists():
        raise FileNotFoundError(
            f"Could not find roles catalog at: {ROLES_PATH}\n"
            f"Create: {DATA_DIR}\\roles.json"
        )

    with open(ROLES_PATH, "r", encoding="utf-8") as f:
        roles = json.load(f)

    # Basic validation
    required_keys = {"id", "title", "category", "description", "top_skills"}
    for r in roles:
        missing = required_keys - set(r.keys())
        if missing:
            raise ValueError(f"Role '{r.get('id', 'UNKNOWN')}' is missing keys: {missing}")
        if not isinstance(r["top_skills"], list):
            raise ValueError(f"Role '{r['id']}' top_skills must be a list")

    return roles


def find_role_by_id(role_id: str, roles: list[dict]):
    return next((r for r in roles if r["id"] == role_id), None)


def normalize_skill(s: str) -> str:
    return s.strip().lower()


# -----------------------------
# Routes
# -----------------------------
@app.get("/")
def home():
    return render_template("home.html")


from werkzeug.utils import secure_filename
from pathlib import Path
import os

ALLOWED_RESUME_EXTS = {".pdf", ".docx"}

@app.route("/profile", methods=["GET", "POST"])
def profile():
    resume_notice = None

    if request.method == "POST":
        degree = request.form.get("degree", "").strip()
        major = request.form.get("major", "").strip()
        location = request.form.get("location", "").strip()

        gpa = request.form.get("gpa", "").strip()
        certifications_raw = request.form.get("certifications", "").strip()
        courses_raw = request.form.get("courses", "").strip()
        skills_raw = request.form.get("skills", "").strip()

        # Turn comma-separated into lists
        user_skills = [s.strip() for s in skills_raw.split(",") if s.strip()]
        user_certs = [c.strip() for c in certifications_raw.split(",") if c.strip()]
        user_courses = [c.strip() for c in courses_raw.split(",") if c.strip()]

        # Load known skills from roles dataset
        roles_data = load_roles()  # your existing function that reads roles.json
        known_skills = sorted({
            skill
            for r in roles_data
            for skill in r.get("skills", [])
        })

        # Resume upload (optional)
        resume_file = request.files.get("resume")
        if resume_file and resume_file.filename:
            original_name = resume_file.filename
            safe_name = secure_filename(original_name)
            ext = Path(safe_name).suffix.lower()

            if ext not in ALLOWED_RESUME_EXTS:
                resume_notice = "Resume upload ignored: please upload a PDF or DOCX file."
            else:
                uploads_dir = Path(__file__).parent / "uploads"
                uploads_dir.mkdir(exist_ok=True)

                save_path = uploads_dir / safe_name
                resume_file.save(str(save_path))

                try:
                    resume_skills = parse_resume_for_skills(str(save_path), known_skills)

                    before_count = len(set(user_skills))
                    user_skills = sorted(set(user_skills) | set(resume_skills))
                    after_count = len(set(user_skills))

                    added = max(0, after_count - before_count)
                    if added > 0:
                        resume_notice = f"Resume parsed successfully — {added} skill(s) added."
                    else:
                        resume_notice = "Resume parsed successfully — no new skills found beyond what you entered."

                except Exception as e:
                    # Don't crash the app if resume parsing fails
                    resume_notice = "Resume upload saved, but we couldn't extract skills from it. You can still continue."
                    # Optional: print(e) for debugging
                    print("Resume parsing error:", e)

        # Store in session
        session["profile"] = {
            "degree": degree,
            "major": major,
            "location": location,
            "gpa": gpa,
            "skills": user_skills,
            "certifications": user_certs,
            "courses": user_courses,
        }

        # If you want the notice to show on the profile page after POST,
        # store it in session temporarily:
        session["resume_notice"] = resume_notice

        return redirect(url_for("roles"))

    # GET
    existing = session.get("profile", {})
    resume_notice = session.pop("resume_notice", None)  # shows once then clears
    return render_template("profile.html", profile=existing, resume_notice=resume_notice)


@app.route("/roles", methods=["GET"])
def roles():
    profile_data = session.get("profile")
    if not profile_data:
        return redirect(url_for("profile"))

    roles_catalog = load_roles()

    query = request.args.get("q", "").strip().lower()
    category = request.args.get("cat", "").strip().lower()

    categories = sorted({r["category"] for r in roles_catalog})

    filtered_roles = []
    for r in roles_catalog:
        matches_query = (
            (not query)
            or (query in r["title"].lower())
            or (query in r["description"].lower())
            or (any(query in sk.lower() for sk in r["top_skills"]))
        )
        matches_cat = (not category) or (category == r["category"].lower())

        if matches_query and matches_cat:
            filtered_roles.append(r)

    return render_template(
        "roles.html",
        profile=profile_data,
        roles=filtered_roles,
        categories=categories,
        q=request.args.get("q", ""),
        cat=request.args.get("cat", ""),
    )


@app.post("/select-role")
def select_role():
    profile_data = session.get("profile")
    if not profile_data:
        return redirect(url_for("profile"))

    role_id = request.form.get("role_id", "").strip()
    if not role_id:
        return redirect(url_for("roles"))

    session["selected_role_id"] = role_id
    return redirect(url_for("results"))


@app.get("/results")
def results():
    profile_data = session.get("profile")
    selected_role_id = session.get("selected_role_id")

    if not profile_data:
        return redirect(url_for("profile"))
    if not selected_role_id:
        return redirect(url_for("roles"))

    roles_catalog = load_roles()
    role = find_role_by_id(selected_role_id, roles_catalog)
    if not role:
        session.pop("selected_role_id", None)
        return redirect(url_for("roles"))

    # -----------------------------
    # Skill gap calculation
    # -----------------------------
    # Base skills from profile
    user_skills = list(profile_data.get("skills", []) or [])

    # Merge in any skills the user has ticked off in progress
    # This means checking off a skill on the progress page actually
    # improves the match score when they come back to results
    existing_progress = session.get("progress", {})
    completed_skills = existing_progress.get("completed", [])
    if completed_skills:
        existing_norm = {normalize_skill(s) for s in user_skills}
        for s in completed_skills:
            if normalize_skill(s) not in existing_norm:
                user_skills.append(s)

    user_skills_norm = {normalize_skill(s) for s in user_skills}

    role_top_skills = role.get("top_skills", []) or []
    role_skills_norm = [normalize_skill(s) for s in role_top_skills]

    missing_skills = [
        role_top_skills[i]
        for i, sk in enumerate(role_skills_norm)
        if sk and sk not in user_skills_norm
    ]

    role_total = max(len(role_top_skills), 1)
    have_count = role_total - len(missing_skills)
    match_score = int(round((have_count / role_total) * 100))

    # -----------------------------
    # Personalized certification suggestions (dummy library)
    # -----------------------------
    CERT_LIBRARY = [
        {
            "name": "Google Data Analytics Professional Certificate",
            "provider": "Coursera",
            "level": "Beginner–Intermediate",
            "skills": ["SQL", "Data Visualization", "Spreadsheets"],
            "tags": ["data", "analytics"],
            "link": ""
        },
        {
            "name": "IBM Data Science Professional Certificate",
            "provider": "Coursera",
            "level": "Intermediate",
            "skills": ["Python", "Machine Learning", "Data Analysis"],
            "tags": ["data", "software"],
            "link": ""
        },
        {
            "name": "Microsoft Azure Fundamentals (AZ-900)",
            "provider": "Microsoft",
            "level": "Beginner",
            "skills": ["Cloud", "Networking", "Security Basics"],
            "tags": ["it", "security", "software"],
            "link": ""
        },
        {
            "name": "CompTIA Security+",
            "provider": "CompTIA",
            "level": "Intermediate",
            "skills": ["Security Basics", "Networking", "Incident Response"],
            "tags": ["security"],
            "link": ""
        },
        {
            "name": "AWS Certified Cloud Practitioner",
            "provider": "AWS",
            "level": "Beginner",
            "skills": ["Cloud", "Networking", "Security Basics"],
            "tags": ["it", "software"],
            "link": ""
        },
        {
            "name": "Google Project Management Professional Certificate",
            "provider": "Coursera",
            "level": "Beginner–Intermediate",
            "skills": ["Project Management", "Communication", "Teamwork"],
            "tags": ["business", "software", "healthcare", "science"],
            "link": ""
        }
    ]

    role_category_tag = (role.get("category", "") or "").strip().lower()
    missing_norm = {normalize_skill(s) for s in missing_skills}

    recommended_certs = []
    for cert in CERT_LIBRARY:
        cert_skill_norm = {normalize_skill(s) for s in cert["skills"]}
        covers_gap = len(missing_norm.intersection(cert_skill_norm)) > 0
        category_match = role_category_tag in [t.lower() for t in cert.get("tags", [])]

        if covers_gap or category_match:
            covered = list(missing_norm.intersection(cert_skill_norm))
            if covered:
                reason = f"Recommended because it helps you build: {', '.join(covered[:3])}."
            else:
                reason = f"Recommended based on your target role in {role.get('category','')}."

            recommended_certs.append({
                "name": cert["name"],
                "provider": cert["provider"],
                "level": cert["level"],
                "skills": cert["skills"],
                "reason": reason,
                "link": cert.get("link", "")
            })

    recommended_certs = recommended_certs[:4]

    # -----------------------------
    # Learning path (dummy)
    # -----------------------------
    recommended_learning = []
    for skill in missing_skills[:4]:
        recommended_learning.append({
            "title": f"{skill} Fundamentals",
            "provider": "edX",
            "skill": skill,
            "format": "Course",
            "link": ""
        })

    # -----------------------------
    # Job listings snapshot (dummy)
    # -----------------------------
    location = profile_data.get("location", "Remote") or "Remote"
    job_listings = [
        {
            "title": f"{role.get('title','Role')} (Entry-Level)",
            "company": "Sample Company A",
            "location": location,
            "skills": role_top_skills[:4],
            "link": ""
        },
        {
            "title": f"Junior {role.get('title','Role')}",
            "company": "Sample Company B",
            "location": location,
            "skills": role_top_skills[1:5],
            "link": ""
        },
        {
            "title": f"{role.get('title','Role')} Intern",
            "company": "Sample Company C",
            "location": "Remote",
            "skills": role_top_skills[:3],
            "link": ""
        }
    ]

    # -----------------------------
    # Results object passed to template
    # -----------------------------
    results_obj = {
        "degree": profile_data.get("degree", ""),
        "location": profile_data.get("location", ""),
        "user_skills": user_skills,
        "selected_role": role.get("title", ""),
        "top_skills_in_jobs": role_top_skills,
        "missing_skills": missing_skills,
        "match_score": match_score,
        "recommended_certs": recommended_certs,
        "recommended_learning": recommended_learning,
        "job_listings": job_listings,
    }

    # -----------------------------
    # Progress checklist setup (NOW results_obj exists)
    # -----------------------------
    progress = session.get("progress")
    if not progress or progress.get("role_id") != selected_role_id:
        session["progress"] = {
            "role_id": selected_role_id,
            "skills": missing_skills,
            "completed": []
        }
    else:
        # keep checklist in sync if role changes slightly
        session["progress"]["skills"] = missing_skills

        # remove completed skills that are no longer in checklist
        session["progress"]["completed"] = [
            s for s in session["progress"].get("completed", [])
            if s in missing_skills
        ]

    return render_template("results.html", results=results_obj)

def normalize_skill(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())

def extract_text_from_pdf(path: str) -> str:
    text = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text.append(page.extract_text() or "")
    return "\n".join(text)

def extract_text_from_docx(path: str) -> str:
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs)

def extract_skills_from_text(text: str, known_skills: list[str]) -> list[str]:
    """Simple keyword scan (safe + explainable for capstone)."""
    t = text.lower()
    found = []
    for sk in known_skills:
        if sk.lower() in t:
            found.append(sk)
    return sorted(set(found))

def parse_resume_for_skills(file_path: str, known_skills: list[str]) -> list[str]:
    if file_path.lower().endswith(".pdf"):
        text = extract_text_from_pdf(file_path)
    elif file_path.lower().endswith(".docx"):
        text = extract_text_from_docx(file_path)
    else:
        return []
    return extract_skills_from_text(text, known_skills)

@app.route("/progress", methods=["GET", "POST"])
def progress():
    data = session.get("progress", {"skills": [], "completed": []})

    if request.method == "POST":
        completed = request.form.getlist("completed")
        # keep only items that are still in the checklist
        allowed = set(data.get("skills", []))
        data["completed"] = [c for c in completed if c in allowed]
        session["progress"] = data

        # Also merge newly-completed skills into the profile so they
        # persist across sessions and show up in results immediately
        profile = session.get("profile", {})
        if profile:
            existing = {normalize_skill(s) for s in profile.get("skills", [])}
            for s in data["completed"]:
                if normalize_skill(s) not in existing:
                    profile.setdefault("skills", []).append(s)
                    existing.add(normalize_skill(s))
            session["profile"] = profile

        return redirect(url_for("progress"))

    return render_template("progress.html", progress=data)

@app.get("/reset")
def reset():
    session.clear()
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)