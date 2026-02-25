from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template, request, redirect, url_for, session
import os
import re
import pdfplumber
from docx import Document
import json
from pathlib import Path
from groq import Groq 
from graph_builder import build_learning_graph
from pathfinder import find_learning_path
from data import courses
import urllib.request

# Build graph once at startup
graph = build_learning_graph(courses)

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-me"  # required for session
from flask_session import Session
import tempfile

app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = tempfile.gettempdir()
app.config["SESSION_PERMANENT"] = False
Session(app)

BROAD_SKILL_TAXONOMY = {
    "Python": ["python"],
    "SQL": ["sql", "mysql", "postgresql", "sqlite"],
    "JavaScript": ["javascript", "js", "node"],
    "Java": ["java"],
    "HTML": ["html"],
    "CSS": ["css"],
    "Git": ["git", "github", "version control"],
    "Data Visualization": ["tableau", "power bi", "matplotlib", "data visualization"],
    "Machine Learning": ["machine learning", "scikit", "tensorflow", "pytorch", "neural network"],
    "Networking": ["networking", "tcp/ip", "cisco", "protocols"],
    "Linux": ["linux", "bash", "shell scripting", "unix"],
    "Security Basics": ["cybersecurity", "security", "encryption", "firewall"],
    "Cloud": ["aws", "azure", "gcp", "cloud", "docker", "kubernetes"],
    "APIs": ["rest api", "restful api", "graphql", "api development"],
    "Problem-solving": ["data structures", "problem solving", "problem-solving"],
    "Communication": ["communication", "presentation", "report writing"],
    "MATLAB": ["matlab"],
    "Excel": ["microsoft excel", "excel spreadsheet"],
    "Research": ["academic research", "research methods"],
}

# -----------------------------
# Resume parsing helpers
# -----------------------------
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
    t = text.lower()
    found = set()

    # Layer 1 — whole-word match against role skills
    for sk in known_skills:
        if re.search(r'\b' + re.escape(sk.lower()) + r'\b', t):
            found.add(sk)

    # Layer 2 — whole-word match against broad taxonomy
    for skill_name, keywords in BROAD_SKILL_TAXONOMY.items():
        for kw in keywords:
            if re.search(r'\b' + re.escape(kw.lower()) + r'\b', t):
                found.add(skill_name)
                break

    # Layer 3 — remove weak single-occurrence matches outside skills context
    weak = set()
    for skill in found:
        skill_lower = skill.lower()
        matches = list(re.finditer(r'\b' + re.escape(skill_lower) + r'\b', t))
        if len(matches) == 1:
            position = matches[0].start()
            surrounding = t[max(0, position-200):position+200]
            skills_context = any(word in surrounding for word in
                ["skill", "technolog", "proficien", "experience", "language", "tool"])
            if not skills_context:
                weak.add(skill)

    found -= weak
    return sorted(found)

def parse_resume_for_skills(file_path: str, known_skills: list[str]) -> list[str]:
    if file_path.lower().endswith(".pdf"):
        text = extract_text_from_pdf(file_path)
    elif file_path.lower().endswith(".docx"):
        text = extract_text_from_docx(file_path)
    else:
        return []

    found = extract_skills_from_text(text, known_skills)
    print("=== RESUME EXTRACTION ===")
    print("Text sample:", text[:300])
    print("Skills found:", found)
    print("=========================")
    return found
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

def score_skill_gaps(missing_skills, all_roles):
    """
    Scores each missing skill by how many roles across the entire
    catalog require it — higher frequency = higher market demand.
    Returns skills sorted by criticality descending.
    """
    frequency = {}
    for role in all_roles:
        for skill in role.get("top_skills", []):
            key = normalize_skill(skill)
            frequency[key] = frequency.get(key, 0) + 1

    total_roles = max(len(all_roles), 1)
    scored = []
    for skill in missing_skills:
        freq = frequency.get(normalize_skill(skill), 0)
        market_score = round((freq / total_roles) * 100)
        priority = (
            "High"   if market_score >= 60 else
            "Medium" if market_score >= 30 else
            "Low"
        )
        scored.append({
            "skill":        skill,
            "market_score": market_score,
            "priority":     priority,
        })

    return sorted(scored, key=lambda x: x["market_score"], reverse=True)

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
            for skill in r.get("top_skills", [])
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
            "optimize_for": request.form.get("optimize_for", "balanced"),
        }

        # If you want the notice to show on the profile page after POST,
        # store it in session temporarily:
        session["resume_notice"] = resume_notice

        return redirect(url_for("survey"))  # ← new

    # GET
    existing = session.get("profile", {})
    resume_notice = session.pop("resume_notice", None)  # shows once then clears
    return render_template("profile.html", profile=existing, resume_notice=resume_notice)


@app.route("/roles", methods=["GET"])
def roles():
    profile_data = session.get("profile", {})

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
        profile=profile_data,  # already defaults to {} now
        roles=filtered_roles,
        categories=categories,
        q=request.args.get("q", ""),
        cat=request.args.get("cat", ""),
    )


@app.post("/select-role")
def select_role():
    role_id = request.form.get("role_id", "").strip()
    if not role_id:
        return redirect(url_for("roles"))

    session["selected_role_id"] = role_id  # ← save FIRST, always
    return redirect(url_for("profile"))

def fetch_youtube_videos(query, max_results=2):
    """Fetch real YouTube videos for a search query."""
    api_key = os.environ.get("YOUTUBE_API_KEY", "")
    if not api_key:
        return []
    try:
        import urllib.parse
        q = urllib.parse.quote(query)
        url = (
            f"https://www.googleapis.com/youtube/v3/search"
            f"?part=snippet&q={q}&type=video&maxResults={max_results}"
            f"&relevanceLanguage=en&key={api_key}"
        )
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read().decode())
        videos = []
        for item in data.get("items", []):
            vid_id = item["id"]["videoId"]
            title  = item["snippet"]["title"]
            thumb  = item["snippet"]["thumbnails"]["medium"]["url"]
            videos.append({
                "title": title,
                "url": f"https://www.youtube.com/watch?v={vid_id}",
                "thumbnail": thumb,
                "video_id": vid_id,
            })
        return videos
    except Exception as e:
        print("YouTube API error:", e)
        return []

@app.get("/results")
def results():
    print("=== RESULTS DEBUG ===")
    print("profile:", session.get("profile"))
    print("selected_role_id:", session.get("selected_role_id"))
    print("=====================")
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

    # ── Skill gap calculation ──────────────────────────
    user_skills = list(profile_data.get("skills", []) or [])

    existing_progress = session.get("progress", {})
    completed_skills = existing_progress.get("completed", [])
    if completed_skills:
        existing_norm = {normalize_skill(s) for s in user_skills}
        for s in completed_skills:
            if normalize_skill(s) not in existing_norm:
                user_skills.append(s)

    user_skills_norm = {normalize_skill(s) for s in user_skills}
    role_top_skills  = role.get("top_skills", []) or []
    role_skills_norm = [normalize_skill(s) for s in role_top_skills]

    missing_skills = [
        role_top_skills[i]
        for i, sk in enumerate(role_skills_norm)
        if sk and sk not in user_skills_norm
    ]

    scored_gaps = score_skill_gaps(missing_skills, roles_catalog)

    role_total  = max(len(role_top_skills), 1)
    have_count  = role_total - len(missing_skills)
    match_score = int(round((have_count / role_total) * 100))

    # ── Certifications ────────────────────────────────
    CERT_LIBRARY = [
        {
            "name": "Google Data Analytics Professional Certificate",
            "provider": "Coursera",
            "level": "Beginner–Intermediate",
            "skills": ["SQL", "Data Visualization", "Spreadsheets"],
            "tags": ["data", "analytics"],
            "link": "https://www.coursera.org/professional-certificates/google-data-analytics"
        },
        {
            "name": "IBM Data Science Professional Certificate",
            "provider": "Coursera",
            "level": "Intermediate",
            "skills": ["Python", "Machine Learning", "Data Analysis"],
            "tags": ["data", "software"],
            "link": "https://www.coursera.org/professional-certificates/ibm-data-science"
        },
        {
            "name": "Microsoft Azure Fundamentals (AZ-900)",
            "provider": "Microsoft",
            "level": "Beginner",
            "skills": ["Cloud", "Networking", "Security Basics"],
            "tags": ["it", "security", "software"],
            "link": "https://learn.microsoft.com/en-us/certifications/azure-fundamentals/"
        },
        {
            "name": "CompTIA Security+",
            "provider": "CompTIA",
            "level": "Intermediate",
            "skills": ["Security Basics", "Networking", "Incident Response"],
            "tags": ["security"],
            "link": "https://www.comptia.org/certifications/security"
        },
        {
            "name": "AWS Certified Cloud Practitioner",
            "provider": "AWS",
            "level": "Beginner",
            "skills": ["Cloud", "Networking", "Security Basics"],
            "tags": ["it", "software"],
            "link": "https://aws.amazon.com/certification/certified-cloud-practitioner/"
        },
        {
            "name": "Google Project Management Certificate",
            "provider": "Coursera",
            "level": "Beginner–Intermediate",
            "skills": ["Project Management", "Communication", "Teamwork"],
            "tags": ["business", "software", "healthcare", "science"],
            "link": "https://www.coursera.org/professional-certificates/google-project-management"
        },
    ]

    role_category_tag = (role.get("category", "") or "").strip().lower()
    missing_norm = {normalize_skill(s) for s in missing_skills}

    recommended_certs = []
    for cert in CERT_LIBRARY:
        cert_skill_norm = {normalize_skill(s) for s in cert["skills"]}
        covers_gap      = len(missing_norm.intersection(cert_skill_norm)) > 0
        category_match  = role_category_tag in [t.lower() for t in cert.get("tags", [])]
        if covers_gap or category_match:
            covered = list(missing_norm.intersection(cert_skill_norm))
            reason  = (
                f"Helps you build: {', '.join(covered[:3])}."
                if covered else
                f"Recommended for {role.get('category','')} roles."
            )
            recommended_certs.append({
                "name":     cert["name"],
                "provider": cert["provider"],
                "level":    cert["level"],
                "skills":   cert["skills"],
                "reason":   reason,
                "link":     cert.get("link", ""),
            })
    recommended_certs = recommended_certs[:4]

    # ── Dijkstra learning paths + YouTube ────────────
    from data import courses as course_catalog
    course_lookup = {c["name"]: c for c in course_catalog}

    optimize_for = profile_data.get("optimize_for", "balanced")
    weight_presets = {
        "time":     {"weight_time": 0.8, "weight_difficulty": 0.1, "weight_cost": 0.1},
        "cost":     {"weight_time": 0.1, "weight_difficulty": 0.1, "weight_cost": 0.8},
        "balanced": {"weight_time": 0.4, "weight_difficulty": 0.3, "weight_cost": 0.3},
        "easy":     {"weight_time": 0.1, "weight_difficulty": 0.8, "weight_cost": 0.1},
    }
    weights = weight_presets.get(optimize_for, weight_presets["balanced"])

    learning_paths = []
    for gap_skill in missing_skills[:4]:
        path, cost = find_learning_path(graph, user_skills, gap_skill, **weights)
        if path and len(path) > 1:
            steps = []
            for i in range(len(path) - 1):
                edge        = graph.get_edge_data(path[i], path[i + 1])
                course_name = edge.get("course", "")
                course_data = course_lookup.get(course_name, {})

                # YouTube: search per step
                yt_query = f"{course_name} tutorial"
                videos   = fetch_youtube_videos(yt_query, max_results=2)

                steps.append({
                    "from":     path[i],
                    "to":       path[i + 1],
                    "course":   course_name,
                    "ms_learn": course_data.get("ms_learn", ""),
                    "youtube_search": course_data.get("youtube", ""),
                    "videos":   videos,
                })
            learning_paths.append({
                "target_skill": gap_skill,
                "path":         path,
                "steps":        steps,
                "total_cost":   round(cost, 1),
            })

    # YouTube: also fetch per skill gap (for the skill section)
    skill_videos = {}
    for gap in missing_skills[:4]:
        skill_videos[gap] = fetch_youtube_videos(
            f"{gap} tutorial for beginners", max_results=2
        )

    # ── Job listings (dummy until Adzuna) ────────────
    location    = profile_data.get("location", "Remote") or "Remote"
    job_listings = [
        {
            "title":    f"{role.get('title','Role')} (Entry-Level)",
            "company":  "Sample Company A",
            "location": location,
            "skills":   role_top_skills[:4],
            "link":     "",
        },
        {
            "title":    f"Junior {role.get('title','Role')}",
            "company":  "Sample Company B",
            "location": location,
            "skills":   role_top_skills[1:5],
            "link":     "",
        },
        {
            "title":    f"{role.get('title','Role')} Intern",
            "company":  "Sample Company C",
            "location": "Remote",
            "skills":   role_top_skills[:3],
            "link":     "",
        },
    ]

    # ── Progress checklist ────────────────────────────
    progress = session.get("progress")
    if not progress or progress.get("role_id") != selected_role_id:
        session["progress"] = {
            "role_id":   selected_role_id,
            "skills":    missing_skills,
            "completed": [],
        }
    else:
        session["progress"]["skills"] = missing_skills
        session["progress"]["completed"] = [
            s for s in session["progress"].get("completed", [])
            if s in missing_skills
        ]

    results_obj = {
        "degree":            profile_data.get("degree", ""),
        "location":          profile_data.get("location", ""),
        "user_skills":       user_skills,
        "selected_role":     role.get("title", ""),
        "top_skills_in_jobs": role_top_skills,
        "missing_skills":    missing_skills,
        "scored_gaps":       scored_gaps,
        "match_score":       match_score,
        "recommended_certs": recommended_certs,
        "learning_paths":    learning_paths,
        "skill_videos":      skill_videos,
        "job_listings":      job_listings,
    }

    return render_template("results.html", results=results_obj)   

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


@app.route("/survey", methods=["GET"])
def survey():
    profile_data = session.get("profile")
    if not profile_data:
        return redirect(url_for("profile"))

    selected_role_id = session.get("selected_role_id")
    role = find_role_by_id(selected_role_id, load_roles()) if selected_role_id else None
    all_role_skills = role.get("top_skills", []) if role else sorted({
        skill for r in load_roles() for skill in r.get("top_skills", [])
    })

    confirmed = set(normalize_skill(s) for s in profile_data.get("skills", []))

    # Filter gaps to tech-relevant skills only
    TECH_SKILLS = {
        "Python", "SQL", "JavaScript", "Java", "HTML", "CSS", "Git",
        "APIs", "Cloud", "Linux", "Machine Learning", "Data Visualization",
        "Networking", "Security Basics", "Problem-solving", "MATLAB", "Research"
    }
    gaps = [s for s in all_role_skills 
            if normalize_skill(s) not in confirmed and s in TECH_SKILLS]

    print("Confirmed skills:", list(confirmed))
    print("Gaps found:", gaps)

    questions = []
    if gaps:
        try:
            degree = profile_data.get("degree", "")
            major = profile_data.get("major", "")

            client = Groq()
            prompt = f"""A Caribbean university student is studying {degree} majoring in {major}.
They have confirmed these skills: {list(confirmed)}.
They are missing these skills relevant to STEM tech careers: {gaps[:10]}.

Generate up to 6 concise survey questions ONLY about technical skills relevant to a {major} student.
Do NOT ask about biology, medicine, or any field unrelated to their degree.
Return ONLY a valid JSON array, no markdown, no explanation:
[
  {{
    "skill": "skill name",
    "question": "the question text",
    "scale_labels": {{"1": "No experience", "3": "Some experience", "5": "Proficient"}}
  }}
]"""

            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = resp.choices[0].message.content.strip()
            raw = re.sub(r"^```json|^```|```$", "", raw, flags=re.MULTILINE).strip()
            questions = json.loads(raw)
        except Exception as e:
            print("Groq error:", e)
            import traceback; traceback.print_exc()
            questions = []

    session["survey_gaps"] = gaps
    return render_template("survey.html", questions=questions, profile=profile_data)


@app.route("/survey/submit", methods=["POST"])
def survey_submit():
    profile_data = session.get("profile", {})
    answers = request.form

    newly_confirmed = [
        skill for skill, score in answers.items()
        if score.isdigit() and int(score) >= 3
    ]

    existing = profile_data.get("skills", [])
    existing_norm = {normalize_skill(s) for s in existing}
    for skill in newly_confirmed:
        if normalize_skill(skill) not in existing_norm:
            existing.append(skill)

    profile_data["skills"] = existing
    session["profile"] = profile_data

    return redirect(url_for("loading"))  # ← change this

#minimal route to set user type for demo purposes (not used in current flow but can be extended later)
@app.route("/set-usertype", methods=["POST"])
def set_usertype():
    session["user_type"] = request.form.get("user_type", "student")
    return redirect(url_for("roles"))

@app.get("/reset")
def reset():
    session.clear()
    return redirect(url_for("roles"))  # ← roles first

@app.get("/loading")
def loading():
    return render_template("loading.html")

if __name__ == "__main__":
    app.run(debug=True)