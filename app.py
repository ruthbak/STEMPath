from flask import Flask, render_template, request, redirect, url_for, session
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


@app.route("/profile", methods=["GET", "POST"])
def profile():
    if request.method == "POST":
        degree = request.form.get("degree", "").strip()
        location = request.form.get("location", "").strip()
        skills_raw = request.form.get("skills", "").strip()

        user_skills = [s.strip() for s in skills_raw.split(",") if s.strip()]

        session["profile"] = {
            "degree": degree,
            "location": location,
            "user_skills": user_skills,
        }

        return redirect(url_for("roles"))

    # Pre-fill profile page if user already has a session
    existing = session.get("profile", {})
    return render_template("profile.html", existing=existing)


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
    user_skills_norm = {normalize_skill(s) for s in profile_data.get("user_skills", [])}
    role_skills_norm = [normalize_skill(s) for s in role["top_skills"]]

    missing_skills = [
        role["top_skills"][i]
        for i, sk in enumerate(role_skills_norm)
        if sk not in user_skills_norm
    ]

    role_total = max(len(role["top_skills"]), 1)
    have_count = role_total - len(missing_skills)
    match_score = int(round((have_count / role_total) * 100))

    # -----------------------------
    # Personalized certification suggestions (dummy but API-ready)
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

    role_category_tag = role["category"].strip().lower()
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
                reason = f"Recommended based on your target role in {role['category']}."

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
            "title": f"{role['title']} (Entry-Level)",
            "company": "Sample Company A",
            "location": location,
            "skills": role["top_skills"][:4],
            "link": ""
        },
        {
            "title": f"Junior {role['title']}",
            "company": "Sample Company B",
            "location": location,
            "skills": role["top_skills"][1:5],
            "link": ""
        },
        {
            "title": f"{role['title']} Intern",
            "company": "Sample Company C",
            "location": "Remote",
            "skills": role["top_skills"][:3],
            "link": ""
        }
    ]

    # -----------------------------
    # Results object passed to template
    # -----------------------------
    results_obj = {
        "degree": profile_data.get("degree", ""),
        "location": profile_data.get("location", ""),
        "user_skills": profile_data.get("user_skills", []),
        "selected_role": role["title"],
        "top_skills_in_jobs": role["top_skills"],
        "missing_skills": missing_skills,
        "match_score": match_score,
        "recommended_certs": recommended_certs,
        "recommended_learning": recommended_learning,
        "job_listings": job_listings,
    }

    return render_template("results.html", results=results_obj)


@app.get("/reset")
def reset():
    session.clear()
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)
