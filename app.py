from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, abort
from functools import wraps
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
from stempath_db import (
    get_latest_profile,
    get_profile,
    get_progress,
    get_user_profiles,
    init_db,
    save_profile,
    save_progress,
    upsert_user,
)
import urllib.request
import urllib.parse

# Build graph once at startup
graph = build_learning_graph(courses)

app = Flask(__name__)
app.config["SECRET_KEY"]              = "dev-secret-key-change-me"
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"]   = False
init_db()

# ── Auth decorator ────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return decorated

# ── Broad skill taxonomy for resume parsing ───────────────────
BROAD_SKILL_TAXONOMY = {
    "Python": ["python", "jupyter", "anaconda"],
    "SQL": ["sql", "mysql", "postgresql", "postgres", "sqlite", "oracle database", "transact-sql"],
    "JavaScript": ["javascript", "js", "node", "node.js", "react", "angular", "vue", "typescript"],
    "Java": ["java", "spring"],
    "HTML": ["html", "html5"],
    "CSS": ["css", "css3", "sass", "bootstrap"],
    "Git": ["git", "github", "gitlab", "bitbucket", "version control"],
    "Data Visualization": ["tableau", "power bi", "matplotlib", "seaborn", "plotly", "data visualization", "dashboard"],
    "Machine Learning": ["machine learning", "scikit", "tensorflow", "pytorch", "neural network", "keras"],
    "Networking": ["networking", "network", "tcp/ip", "cisco", "protocols", "router", "switch"],
    "Linux": ["linux", "bash", "shell scripting", "unix"],
    "Security Basics": ["cybersecurity", "security", "encryption", "firewall", "splunk", "siem"],
    "Cloud": ["aws", "azure", "gcp", "google cloud", "cloud", "docker", "kubernetes"],
    "APIs": ["rest api", "restful api", "graphql", "api development", "postman"],
    "Problem-solving": ["data structures", "problem solving", "problem-solving"],
    "Communication": ["communication", "presentation", "report writing"],
    "MATLAB": ["matlab"],
    "Excel": ["microsoft excel", "excel", "spreadsheet"],
    "Research": ["academic research", "research methods", "research", "labview"],
    "Statistics": ["statistics", "statistical analysis", "spss", "sas", "rstudio"],
}

# ── Resume parsing ────────────────────────────────────────────
def extract_text_from_pdf(path):
    text = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text.append(page.extract_text() or "")
    return "\n".join(text)

def extract_text_from_docx(path):
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs)

def extract_skills_from_text(text, known_skills):
    t = text.lower()
    found = set()
    for sk in known_skills:
        if re.search(r'\b' + re.escape(sk.lower()) + r'\b', t):
            found.add(sk)
    for skill_name, keywords in BROAD_SKILL_TAXONOMY.items():
        for kw in keywords:
            if re.search(r'\b' + re.escape(kw.lower()) + r'\b', t):
                found.add(skill_name)
                break
    weak = set()
    for skill in found:
        matches = list(re.finditer(r'\b' + re.escape(skill.lower()) + r'\b', t))
        if len(matches) == 1:
            position   = matches[0].start()
            surrounding = t[max(0, position-200):position+200]
            if not any(w in surrounding for w in ["skill", "technolog", "proficien", "experience", "language", "tool"]):
                weak.add(skill)
    found -= weak
    return sorted(found)

def parse_resume_for_skills(file_path, known_skills):
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
    return found

# ── Roles catalog helpers ─────────────────────────────────────
BASE_DIR   = Path(__file__).parent
DATA_DIR   = BASE_DIR / "data"
ROLES_PATH = DATA_DIR / "roles.json"

def load_roles():
    if not ROLES_PATH.exists():
        raise FileNotFoundError(f"Could not find roles catalog at: {ROLES_PATH}")
    with open(ROLES_PATH, "r", encoding="utf-8") as f:
        roles = json.load(f)
    required_keys = {"id", "title", "category", "description", "top_skills"}
    for r in roles:
        missing = required_keys - set(r.keys())
        if missing:
            raise ValueError(f"Role '{r.get('id','UNKNOWN')}' missing keys: {missing}")
        if not isinstance(r["top_skills"], list):
            raise ValueError(f"Role '{r['id']}' top_skills must be a list")
    return roles

def find_role_by_id(role_id, roles):
    return next((r for r in roles if r["id"] == role_id), None)

def normalize_skill(s):
    return s.strip().lower()

def get_graph_skills():
    supported = set()
    for c in courses:
        supported.update(c.get("teaches", []))
        supported.update(c.get("prerequisites", []))
    supported.discard("ROOT")
    return supported

def score_skill_gaps(missing_skills, all_roles):
    frequency = {}
    for role in all_roles:
        for skill in role.get("top_skills", []):
            key = normalize_skill(skill)
            frequency[key] = frequency.get(key, 0) + 1
    total_roles = max(len(all_roles), 1)
    scored = []
    for skill in missing_skills:
        freq         = frequency.get(normalize_skill(skill), 0)
        market_score = round((freq / total_roles) * 100)
        priority     = "High" if market_score >= 60 else "Medium" if market_score >= 30 else "Low"
        scored.append({"skill": skill, "market_score": market_score, "priority": priority})
    return sorted(scored, key=lambda x: x["market_score"], reverse=True)

# ── YouTube helper ────────────────────────────────────────────
def fetch_youtube_videos(query, max_results=2):
    api_key = os.environ.get("YOUTUBE_API_KEY", "")
    if not api_key:
        return []
    try:
        import urllib.parse
        q   = urllib.parse.quote(query)
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
                "title":     title,
                "url":       f"https://www.youtube.com/watch?v={vid_id}",
                "thumbnail": thumb,
                "video_id":  vid_id,
                "embed_url": f"https://www.youtube.com/embed/{vid_id}",
            })
        return videos
    except Exception as e:
        print("YouTube API error:", e)
        return []


def microsoft_learn_search_url(query):
    return f"https://learn.microsoft.com/en-us/search/?terms={urllib.parse.quote(query)}"


SKILL_CHECK_QUESTIONS = {
    "python": {
        "question": "What is the output of this Python code: for i in range(3): print(i)",
        "options": ["0 1 2", "1 2 3", "0 1 2 3", "The code raises a syntax error"],
        "answer": "0 1 2",
        "explanation": "range(3) produces 0, 1, and 2.",
    },
    "sql": {
        "question": "Which SQL clause is used to filter rows before grouping or sorting?",
        "options": ["WHERE", "ORDER BY", "GROUP BY", "SELECT"],
        "answer": "WHERE",
        "explanation": "WHERE filters rows before GROUP BY and ORDER BY are applied.",
    },
    "statistics": {
        "question": "Which measure best describes the middle value of an ordered dataset?",
        "options": ["Median", "Range", "Variance", "Standard deviation"],
        "answer": "Median",
        "explanation": "The median is the middle value when observations are ordered.",
    },
    "machine learning": {
        "question": "What is the main purpose of a train/test split?",
        "options": [
            "To evaluate a model on data it did not train on",
            "To delete missing values",
            "To make every feature numeric",
            "To increase the number of rows",
        ],
        "answer": "To evaluate a model on data it did not train on",
        "explanation": "A test set estimates how well the model generalizes to unseen data.",
    },
    "data visualization": {
        "question": "Which chart is usually best for showing a trend over time?",
        "options": ["Line chart", "Pie chart", "Box plot", "Scatter plot"],
        "answer": "Line chart",
        "explanation": "Line charts make changes over time easy to follow.",
    },
    "networking": {
        "question": "Which OSI layer is responsible for IP addressing and routing?",
        "options": ["Network layer", "Application layer", "Data link layer", "Physical layer"],
        "answer": "Network layer",
        "explanation": "Layer 3, the network layer, handles logical addressing and routing.",
    },
    "linux": {
        "question": "Which Linux command lists files in the current directory?",
        "options": ["ls", "cd", "pwd", "mkdir"],
        "answer": "ls",
        "explanation": "ls lists directory contents.",
    },
    "security basics": {
        "question": "What does multi-factor authentication add to a login process?",
        "options": [
            "An extra proof of identity beyond a password",
            "A faster internet connection",
            "Automatic software updates",
            "A public IP address",
        ],
        "answer": "An extra proof of identity beyond a password",
        "explanation": "MFA requires another factor, such as a code or device, in addition to a password.",
    },
    "cloud": {
        "question": "Which cloud model gives teams virtual servers, storage, and networking to manage?",
        "options": ["IaaS", "SaaS", "HTML", "DNS"],
        "answer": "IaaS",
        "explanation": "Infrastructure as a Service provides compute, storage, and network resources.",
    },
    "git": {
        "question": "Which Git command records staged changes in the repository history?",
        "options": ["git commit", "git status", "git clone", "git branch"],
        "answer": "git commit",
        "explanation": "git commit saves staged changes as a new commit.",
    },
    "apis": {
        "question": "In a REST API, which HTTP method is commonly used to retrieve data?",
        "options": ["GET", "POST", "PATCH", "DELETE"],
        "answer": "GET",
        "explanation": "GET requests retrieve resources without modifying them.",
    },
    "javascript": {
        "question": "Which JavaScript keyword declares a block-scoped variable?",
        "options": ["let", "var", "def", "echo"],
        "answer": "let",
        "explanation": "let declares a variable scoped to the nearest block.",
    },
    "html": {
        "question": "Which HTML element is used for the largest page heading?",
        "options": ["h1", "head", "title", "section"],
        "answer": "h1",
        "explanation": "h1 represents the top-level heading in page content.",
    },
    "css": {
        "question": "Which CSS property changes the text color of an element?",
        "options": ["color", "font-style", "background-color", "display"],
        "answer": "color",
        "explanation": "The color property controls foreground text color.",
    },
    "java": {
        "question": "Which Java keyword is used to define a class?",
        "options": ["class", "def", "function", "module"],
        "answer": "class",
        "explanation": "Java uses the class keyword to define classes.",
    },
    "excel": {
        "question": "Which Excel formula adds the values in cells A1 through A5?",
        "options": ["=SUM(A1:A5)", "=ADD(A1-A5)", "=TOTAL(A1,A5)", "=COUNT(A1:A5)"],
        "answer": "=SUM(A1:A5)",
        "explanation": "SUM adds all numeric values in the selected range.",
    },
    "research": {
        "question": "Why is a literature review useful before starting a research project?",
        "options": [
            "It shows what is already known and where gaps exist",
            "It replaces the need for data collection",
            "It guarantees the hypothesis is correct",
            "It removes the need to cite sources",
        ],
        "answer": "It shows what is already known and where gaps exist",
        "explanation": "A literature review helps position new work against existing evidence.",
    },
    "communication": {
        "question": "What is the clearest way to present a technical recommendation to a non-technical audience?",
        "options": [
            "Start with the decision and explain the impact in plain language",
            "Use as many acronyms as possible",
            "Show only raw data tables",
            "Avoid mentioning tradeoffs",
        ],
        "answer": "Start with the decision and explain the impact in plain language",
        "explanation": "Good communication adapts the message to the audience.",
    },
    "matlab": {
        "question": "In MATLAB, which symbol is commonly used for element-wise multiplication?",
        "options": [".*", "*", "x", "mul()"],
        "answer": ".*",
        "explanation": ".* multiplies corresponding elements in arrays.",
    },
}


def _skill_check_for(skill):
    normalized = normalize_skill(skill)
    if normalized in SKILL_CHECK_QUESTIONS:
        return SKILL_CHECK_QUESTIONS[normalized]

    for key, check in SKILL_CHECK_QUESTIONS.items():
        if key in normalized or normalized in key:
            return check

    return {
        "question": f"Which answer best shows practical understanding of {skill}?",
        "options": [
            f"I can explain when to use {skill} and apply it in a small task",
            f"I have only heard the term {skill}",
            f"{skill} is unrelated to technical work",
            f"I would always skip {skill} in a project",
        ],
        "answer": f"I can explain when to use {skill} and apply it in a small task",
        "explanation": f"This checks whether you can apply {skill}, not just recognize the term.",
    }


def _question_for_skill(skill, reason):
    check = _skill_check_for(skill)
    return {
        "skill": skill,
        "reason": reason,
        "question": check["question"],
        "options": check["options"],
        "answer": check["answer"],
        "explanation": check["explanation"],
    }


def build_dynamic_survey_questions(profile_data, role):
    role_skills = role.get("top_skills", []) if role else []
    claimed_skills = profile_data.get("skills", []) or []
    claimed_norm = {normalize_skill(s) for s in claimed_skills}

    claimed_target_skills = [
        skill for skill in role_skills
        if normalize_skill(skill) in claimed_norm
    ]
    missing_target_skills = [
        skill for skill in role_skills
        if normalize_skill(skill) not in claimed_norm
    ]

    # The count is data-driven: validate up to three claimed role skills,
    # then ask about the highest-priority gaps. This avoids a fixed survey size.
    validate_count = min(3, len(claimed_target_skills))
    gap_count = min(7 - validate_count, len(missing_target_skills))

    questions = [
        _question_for_skill(skill, "validate_claimed")
        for skill in claimed_target_skills[:validate_count]
    ]
    questions.extend(
        _question_for_skill(skill, "assess_gap")
        for skill in missing_target_skills[:gap_count]
    )

    rationale = {
        "claimed_target_count": len(claimed_target_skills),
        "missing_target_count": len(missing_target_skills),
        "validate_count": validate_count,
        "gap_count": gap_count,
        "total": len(questions),
    }
    return questions, rationale, missing_target_skills


def build_graph_overview(graph):
    skill_nodes = [
        n for n in graph.nodes
        if n != "ROOT" and not str(n).startswith("GATE::")
    ]
    gate_nodes = [n for n in graph.nodes if str(n).startswith("GATE::")]
    edges = []
    visual_edges = []
    visual_nodes = set()
    for source, target, data in graph.edges(data=True):
        course = data.get("course", "")
        if course == "return_to_root":
            continue
        visual_nodes.update([source, target])
        edges.append({
            "from": source,
            "to": target,
            "course": course,
            "time": data.get("time", 0),
            "difficulty": data.get("difficulty", 0),
            "cost": data.get("cost", 0),
            "is_gate_check": course.startswith("prereq_check::"),
        })
        visual_edges.append({
            "from": source,
            "to": target,
            "course": course,
            "is_gate_check": course.startswith("prereq_check::"),
        })

    prereq_targets = {edge["to"] for edge in visual_edges}
    levels = {"ROOT": 0}
    for node in visual_nodes:
        if node not in levels:
            levels[node] = 1 if node not in prereq_targets else 2

    changed = True
    while changed:
        changed = False
        for edge in visual_edges:
            source_level = levels.get(edge["from"], 1)
            target_level = levels.get(edge["to"], 1)
            next_level = min(source_level + 1, 5)
            if next_level > target_level:
                levels[edge["to"]] = next_level
                changed = True

    grouped = {}
    for node in visual_nodes:
        grouped.setdefault(levels.get(node, 1), []).append(node)

    graph_nodes = []
    for level in sorted(grouped):
        nodes = sorted(grouped[level])
        for index, node in enumerate(nodes):
            count = len(nodes)
            graph_nodes.append({
                "id": re.sub(r"[^a-zA-Z0-9_-]", "_", str(node)),
                "label": str(node).replace("GATE::", "Gate: "),
                "raw": node,
                "level": level,
                "x": 80 + (level * 165),
                "y": 70 + (index + 1) * (420 / (count + 1)),
                "type": (
                    "root" if node == "ROOT"
                    else "gate" if str(node).startswith("GATE::")
                    else "skill"
                ),
            })
    node_ids = {node["raw"]: node["id"] for node in graph_nodes}
    node_lookup = {node["raw"]: node for node in graph_nodes}
    graph_visual = {
        "nodes": graph_nodes,
        "layers": [
            {
                "level": level,
                "title": "Start" if level == 0 else f"Layer {level}",
                "nodes": [
                    {
                        "label": str(node).replace("GATE::", "Gate: "),
                        "raw": node,
                        "type": (
                            "root" if node == "ROOT"
                            else "gate" if str(node).startswith("GATE::")
                            else "skill"
                        ),
                    }
                    for node in sorted(grouped[level])
                ],
            }
            for level in sorted(grouped)
        ],
        "edges": [
            {
                **edge,
                "from_id": node_ids.get(edge["from"], ""),
                "to_id": node_ids.get(edge["to"], ""),
                "from_x": node_lookup.get(edge["from"], {}).get("x", 0),
                "from_y": node_lookup.get(edge["from"], {}).get("y", 0),
                "to_x": node_lookup.get(edge["to"], {}).get("x", 0),
                "to_y": node_lookup.get(edge["to"], {}).get("y", 0),
            }
            for edge in visual_edges
        ],
    }

    return {
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "skill_nodes": sorted(skill_nodes),
        "gate_nodes": sorted(gate_nodes),
        "edges": sorted(edges, key=lambda e: (str(e["from"]), str(e["to"]), str(e["course"]))),
        "visual": graph_visual,
        "cost_formula": "time x weight_time + difficulty x weight_difficulty + cost x weight_cost",
    }

# ── Build recommended learning ────────────────────────────────
def build_recommended_learning(learning_paths):
    items = []
    for lp in learning_paths:
        real_steps = [
            s for s in lp.get("steps", [])
            if s.get("course")
            and s["course"] != "return_to_root"
            and not s["course"].startswith("prereq_check::")
        ]
        if not real_steps:
            continue
        final_step     = real_steps[-1]
        learning_nodes = []
        for step in real_steps:
            to_node = step.get("to", "")
            if to_node and to_node != "ROOT" and not str(to_node).startswith("GATE::"):
                if not learning_nodes or learning_nodes[-1] != to_node:
                    learning_nodes.append(to_node)
        if not learning_nodes:
            continue
        prereqs   = learning_nodes[:-1] if len(learning_nodes) > 1 else []
        edx_link  = final_step.get("edx_link") or final_step.get("edx", "")
        ms_link   = final_step.get("ms_learn_search") or final_step.get("ms_learn") or final_step.get("microsoft", "")
        best_link = edx_link or ms_link or ""
        if edx_link:
            provider = final_step.get("provider") or "edX"
        elif ms_link:
            provider = "Microsoft Learn"
        else:
            provider = final_step.get("provider") or "edX / Coursera"
        items.append({
            "skill":      lp.get("target_skill", ""),
            "title":      final_step.get("course", ""),
            "provider":   provider,
            "format":     "Guided path",
            "link":       best_link,
            "path":       learning_nodes,
            "prereqs":    prereqs,
            "total_cost": round(lp.get("total_cost", 0), 1),
        })
    return items

# ── Cert library ──────────────────────────────────────────────
CERT_LIBRARY = [
    {"name": "Google Data Analytics Professional Certificate", "provider": "Coursera",
     "level": "Beginner–Intermediate", "skills": ["SQL", "Data Visualization", "Spreadsheets", "Data Analysis"],
     "tags": ["data", "analytics", "software", "technology"],
     "link": "https://www.coursera.org/professional-certificates/google-data-analytics"},
    {"name": "IBM Data Science Professional Certificate", "provider": "Coursera",
     "level": "Intermediate", "skills": ["Python", "Machine Learning", "Data Analysis", "SQL"],
     "tags": ["data", "software", "science", "technology"],
     "link": "https://www.coursera.org/professional-certificates/ibm-data-science"},
    {"name": "Microsoft Azure Fundamentals (AZ-900)", "provider": "Microsoft",
     "level": "Beginner", "skills": ["Cloud", "Networking", "Security Basics"],
     "tags": ["it", "security", "software", "technology"],
     "link": "https://learn.microsoft.com/en-us/certifications/azure-fundamentals/"},
    {"name": "CompTIA Security+", "provider": "CompTIA",
     "level": "Intermediate", "skills": ["Security Basics", "Networking", "Incident Response", "Linux"],
     "tags": ["security", "it", "technology"],
     "link": "https://www.comptia.org/certifications/security"},
    {"name": "AWS Certified Cloud Practitioner", "provider": "AWS",
     "level": "Beginner", "skills": ["Cloud", "Networking", "Security Basics"],
     "tags": ["it", "software", "technology"],
     "link": "https://aws.amazon.com/certification/certified-cloud-practitioner/"},
    {"name": "Google Project Management Certificate", "provider": "Coursera",
     "level": "Beginner–Intermediate", "skills": ["Project Management", "Communication", "Teamwork"],
     "tags": ["business", "software", "healthcare", "science", "engineering", "technology"],
     "link": "https://www.coursera.org/professional-certificates/google-project-management"},
    {"name": "Meta Front-End Developer Certificate", "provider": "Coursera / Meta",
     "level": "Beginner–Intermediate", "skills": ["JavaScript", "HTML", "CSS", "React", "APIs"],
     "tags": ["software", "it", "technology"],
     "link": "https://www.coursera.org/professional-certificates/meta-front-end-developer"},
    {"name": "Google IT Support Professional Certificate", "provider": "Coursera / Google",
     "level": "Beginner", "skills": ["Networking", "Linux", "Security Basics", "Cloud"],
     "tags": ["it", "security", "technology"],
     "link": "https://www.coursera.org/professional-certificates/google-it-support"},
    {"name": "AutoCAD Certified Professional", "provider": "Autodesk",
     "level": "Intermediate", "skills": ["AutoCAD", "Technical Drawing", "CAD"],
     "tags": ["engineering", "mechanical", "civil"],
     "link": "https://www.autodesk.com/certification/all-certifications/autocad"},
    {"name": "MATLAB Fundamentals", "provider": "MathWorks",
     "level": "Beginner–Intermediate", "skills": ["MATLAB", "Simulation", "Signal Processing", "Data Analysis"],
     "tags": ["engineering", "science", "physics", "mathematics"],
     "link": "https://www.mathworks.com/learn/training/matlab-fundamentals.html"},
    {"name": "Six Sigma Green Belt", "provider": "ASQ",
     "level": "Intermediate", "skills": ["Quality Control", "Statistical Analysis", "Process Improvement"],
     "tags": ["engineering", "mechanical", "industrial"],
     "link": "https://asq.org/cert/six-sigma-green-belt"},
    {"name": "PMP — Project Management Professional", "provider": "PMI",
     "level": "Advanced", "skills": ["Project Management", "Communication", "Risk Management", "Teamwork"],
     "tags": ["engineering", "software", "science", "business"],
     "link": "https://www.pmi.org/certifications/project-management-pmp"},
    {"name": "Medical Imaging Fundamentals (edX)", "provider": "edX",
     "level": "Intermediate", "skills": ["Medical Imaging", "Radiation Physics", "MATLAB", "Data Analysis"],
     "tags": ["healthcare", "physics", "science"],
     "link": "https://www.edx.org/learn/medical-imaging"},
    {"name": "Radiation Protection Supervisor Certificate", "provider": "IAEA / National Bodies",
     "level": "Intermediate", "skills": ["Radiation Safety", "Dosimetry", "Radiation Physics"],
     "tags": ["healthcare", "physics", "science"],
     "link": "https://www.iaea.org/resources/rpop/health-professionals/radiation-therapy/medical-physics"},
    {"name": "Google Health Data Analytics", "provider": "Coursera",
     "level": "Intermediate", "skills": ["Data Analysis", "Research", "Communication", "Excel"],
     "tags": ["healthcare", "science", "data"],
     "link": "https://www.coursera.org/learn/health-data-analytics"},
    {"name": "IBM Data Analyst Professional Certificate", "provider": "Coursera / IBM",
     "level": "Beginner–Intermediate", "skills": ["Python", "SQL", "Excel", "Data Visualization", "Research"],
     "tags": ["science", "data", "analytics"],
     "link": "https://www.coursera.org/professional-certificates/ibm-data-analyst"},
    {"name": "Research Methods and Statistics (Coursera)", "provider": "Coursera",
     "level": "Beginner–Intermediate", "skills": ["Research", "Statistical Analysis", "Data Analysis", "Communication"],
     "tags": ["science", "healthcare", "engineering"],
     "link": "https://www.coursera.org/learn/research-methods"},
]

# ── STEM category map for roles filter ───────────────────────
STEM_MAP = {
    "Science":     ["science", "life science", "physical science", "environmental science",
                    "medical physics", "physics", "chemistry", "biology"],
    "Technology":  ["technology", "it", "software", "computing", "data science",
                    "cybersecurity", "information technology", "computer science"],
    "Engineering": ["engineering", "civil engineering", "mechanical engineering",
                    "electrical engineering", "chemical engineering"],
    "Mathematics": ["mathematics", "math", "statistics", "statistical", "actuarial",
                    "actuary", "operations research"],
}


def role_matches_stem_category(role, category):
    """Match broad STEM buttons against category labels and role content."""
    if not category:
        return True

    aliases = [c.lower() for c in STEM_MAP.get(category, [category.lower()])]
    role_cat_lower = role.get("category", "").strip().lower()

    if category != "Mathematics":
        return role_cat_lower in aliases or any(alias in role_cat_lower for alias in aliases)

    role_text = " ".join([
        role.get("category", ""),
        role.get("title", ""),
        role.get("description", ""),
    ]).lower()

    return any(alias in role_text for alias in aliases)


def survey_status_by_skill(survey_scores):
    return {
        normalize_skill(item.get("skill", "")): item.get("status")
        for item in survey_scores or []
        if item.get("skill")
    }


def apply_survey_evidence_to_skills(user_skills, completed_skills, survey_scores):
    """
    Use survey evidence for pathway planning without rewriting the saved profile.

    - Completed progress skills always count.
    - Claimed skills that failed validation are removed from Dijkstra start skills.
    - Claimed skills that passed validation stay available.
    - Correct answers for missing/gap skills show familiarity, but do not count as mastery.
    """
    status_by_norm = survey_status_by_skill(survey_scores)
    completed_norm = {normalize_skill(s) for s in completed_skills or []}
    effective_skills = []
    effective_norm = set()

    for skill in user_skills:
        norm = normalize_skill(skill)
        if not norm:
            continue
        if status_by_norm.get(norm) == "needs_review" and norm not in completed_norm:
            continue
        if norm not in effective_norm:
            effective_skills.append(skill)
            effective_norm.add(norm)

    for skill in completed_skills or []:
        norm = normalize_skill(skill)
        if norm and norm not in effective_norm:
            effective_skills.append(skill)
            effective_norm.add(norm)

    return effective_skills


def prioritize_missing_skills_with_survey(missing_skills, survey_scores):
    status_by_norm = survey_status_by_skill(survey_scores)
    priority = {
        "needs_review": 0,
        "learning_gap": 0,
        None: 1,
        "familiarity_shown": 2,
        "confirmed": 3,
    }

    return [
        skill for _, skill in sorted(
            enumerate(missing_skills),
            key=lambda item: (
                priority.get(status_by_norm.get(normalize_skill(item[1])), 1),
                item[0],
            ),
        )
    ]

"""The pathway roadmap """
def get_roadmap_icon(skill):
    skill = (skill or "").lower()

    icon_rules = {
        ("python",): "🐍",
        ("linux",): "🐧",
        ("excel", "spreadsheet"): "📊",
        ("research", "laboratory", "lab"): "🔬",
        ("statistics", "probability", "math", "calculus", "linear algebra"): "➗",
        ("sql", "database"): "🗄️",
        ("data", "analytics", "visualization", "tableau", "power bi"): "📈",
        ("machine learning", "ai", "artificial intelligence"): "🤖",
        ("cloud", "aws", "azure"): "☁️",
        ("security", "cyber"): "🔒",
        ("network",): "🌐",
        ("web", "html", "css", "javascript", "react"): "💻",
        ("matlab",): "📐",
        ("physics",): "⚛️",
        ("radiation", "dosimetry", "medical imaging"): "🩻",
        ("cad", "autocad", "solidworks", "design"): "🛠️",
        ("engineering",): "⚙️",
        ("communication", "leadership", "teamwork"): "🗣️",
    }

    for keywords, icon in icon_rules.items():
        if any(keyword in skill for keyword in keywords):
            return icon

    return "📍"


def build_roadmap_steps(results, max_steps=8):
    roadmap_steps = []
    seen_skills = set()

    selected_role = results.get("selected_role", "your selected career")

    # Use actual missing skills first, not Dijkstra intermediate steps
    for skill in results.get("missing_skills", []):
        if not skill:
            continue

        skill_key = skill.strip().lower()

        if skill_key in seen_skills:
            continue

        seen_skills.add(skill_key)

        roadmap_steps.append({
            "skill": skill,
            "icon": get_roadmap_icon(skill),
            "description": (
                f"Build this skill to strengthen your alignment with "
                f"{selected_role} roles."
            )
        })

        if len(roadmap_steps) >= max_steps:
            break

    return roadmap_steps

# ── Routes ────────────────────────────────────────────────────
@app.get("/")
def home():
    return render_template("home.html")

from werkzeug.utils import secure_filename
ALLOWED_RESUME_EXTS = {".pdf", ".docx"}

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    resume_notice = None
    if request.method == "POST":
        user_id            = session.get("user_id")
        degree             = request.form.get("degree", "").strip()
        degree             = ", ".join([d.strip() for d in degree.split(",") if d.strip()][:2])
        major              = request.form.get("major", "").strip()
        location           = request.form.get("location", "").strip()
        gpa                = request.form.get("gpa", "").strip()
        certifications_raw = request.form.get("certifications", "").strip()
        courses_raw        = request.form.get("courses", "").strip()
        skills_raw         = request.form.get("skills", "").strip()

        user_skills  = [s.strip() for s in skills_raw.split(",")         if s.strip()]
        user_certs   = [c.strip() for c in certifications_raw.split(",") if c.strip()]
        user_courses = [c.strip() for c in courses_raw.split(",")        if c.strip()]
        resume_path  = None

        roles_data   = load_roles()
        known_skills = sorted({skill for r in roles_data for skill in r.get("top_skills", [])})

        resume_file = request.files.get("resume")
        if resume_file and resume_file.filename:
            safe_name = secure_filename(resume_file.filename)
            ext       = Path(safe_name).suffix.lower()
            if ext not in ALLOWED_RESUME_EXTS:
                resume_notice = "Resume upload ignored: please upload a PDF or DOCX file."
            else:
                uploads_dir = Path(__file__).parent / "uploads"
                uploads_dir.mkdir(exist_ok=True)
                save_path = uploads_dir / safe_name
                resume_file.save(str(save_path))
                resume_path = str(save_path)
                try:
                    resume_skills = parse_resume_for_skills(str(save_path), known_skills)
                    before        = len(set(user_skills))
                    user_skills   = sorted(set(user_skills) | set(resume_skills))
                    added         = max(0, len(set(user_skills)) - before)
                    resume_notice = (
                        f"Resume parsed — {added} skill(s) added." if added > 0
                        else "Resume parsed — no new skills found beyond what you entered."
                    )
                except Exception as e:
                    resume_notice = "Resume saved but we couldn't extract skills from it."
                    print("Resume parsing error:", e)

        profile_data = {
            "degree":         degree,
            "major":          major,
            "location":       location,
            "gpa":            gpa,
            "skills":         user_skills,
            "certifications": user_certs,
            "courses":        user_courses,
            "optimize_for":   request.form.get("optimize_for", "balanced"),
        }

        saved_profile = save_profile(
            user_id,
            profile_data,
            profile_id=session.get("active_profile_id"),
            resume_path=resume_path,
            create_new=session.pop("create_new_profile", False),
        )

        session["profile"] = saved_profile or profile_data
        if saved_profile:
            session["active_profile_id"] = saved_profile["id"]
        session["resume_notice"] = resume_notice
        session["flash"]         = "Profile saved successfully!"

        if session.get("selected_role_id"):
            return redirect(url_for("survey"))
        else:
            return redirect(url_for("roles"))

    existing = get_latest_profile(session.get("user_id")) or session.get("profile", {})
    if existing:
        session["profile"] = existing
        session["active_profile_id"] = existing.get("id")
    resume_notice = session.pop("resume_notice", None)
    selected_role = None
    selected_role_id = session.get("selected_role_id")
    if selected_role_id:
        selected_role = find_role_by_id(selected_role_id, load_roles())

    return render_template(
        "profile.html",
        profile=existing,
        resume_notice=resume_notice,
        selected_role=selected_role,
    )


@app.get("/profile/new")
@login_required
def new_profile():
    session.pop("profile", None)
    session.pop("active_profile_id", None)
    session["create_new_profile"] = True
    return redirect(url_for("profile"))


@app.get("/profile/<int:profile_id>")
@login_required
def open_profile(profile_id):
    profile_data = get_profile(session.get("user_id"), profile_id)
    if not profile_data:
        abort(403)

    session["profile"] = profile_data
    session["active_profile_id"] = profile_data["id"]
    return redirect(url_for("profile"))


@app.route("/roles", methods=["GET"])
@login_required
def roles():
    profile_data   = get_latest_profile(session.get("user_id")) or session.get("profile", {})
    if profile_data:
        session["profile"] = profile_data
        session["active_profile_id"] = profile_data.get("id")
    roles_catalog  = load_roles()
    query          = request.args.get("q", "").strip().lower()
    category       = request.args.get("cat", "").strip()
    categories     = sorted({r["category"] for r in roles_catalog})
    filtered_roles = []

    for r in roles_catalog:
        matches_query = (
            not query
            or query in r["title"].lower()
            or query in r["description"].lower()
            or any(query in sk.lower() for sk in r["top_skills"])
        )
        if not category:
            matches_cat = True
        else:
            matches_cat = role_matches_stem_category(r, category)
        if matches_query and matches_cat:
            filtered_roles.append(r)

    return render_template(
        "roles.html",
        profile=profile_data,
        roles=filtered_roles,
        categories=categories,
        q=request.args.get("q", ""),
        cat=category,
    )


@app.post("/select-role")
def select_role():
    role_id = request.form.get("role_id", "").strip()
    if not role_id:
        return redirect(url_for("roles"))
    session["selected_role_id"] = role_id
    return redirect(url_for("profile"))


@app.get("/results")
@login_required
def results():
    print("=== RESULTS DEBUG ===")
    print("profile:", session.get("profile"))
    print("selected_role_id:", session.get("selected_role_id"))
    print("=====================")
    profile_data = get_latest_profile(session.get("user_id")) or session.get("profile")
    if profile_data:
        session["profile"] = profile_data
        session["active_profile_id"] = profile_data.get("id")
    selected_role_id = session.get("selected_role_id")

    if not profile_data:
        return redirect(url_for("profile"))
    if not selected_role_id:
        return redirect(url_for("roles"))

    roles_catalog = load_roles()
    role          = find_role_by_id(selected_role_id, roles_catalog)
    if not role:
        session.pop("selected_role_id", None)
        return redirect(url_for("roles"))

    # ── Skill gap ──────────────────────────────────────
    profile_skills = list(profile_data.get("skills", []) or [])
    user_skills = list(profile_skills)

    existing_progress = get_progress(
        session.get("user_id"),
        profile_id=session.get("active_profile_id"),
        role_id=selected_role_id,
    )
    completed_skills = existing_progress.get("completed", [])
    if completed_skills:
        existing_norm = {normalize_skill(s) for s in user_skills}
        for s in completed_skills:
            if normalize_skill(s) not in existing_norm:
                user_skills.append(s)

    survey_scores = session.get("survey_scores", [])
    survey_summary = session.get("survey_summary", {})
    user_skills = apply_survey_evidence_to_skills(user_skills, completed_skills, survey_scores)

    user_skills_norm = {normalize_skill(s) for s in user_skills}
    role_top_skills  = role.get("top_skills", []) or []
    role_skills_norm = [normalize_skill(s) for s in role_top_skills]

    missing_skills = prioritize_missing_skills_with_survey([
        role_top_skills[i]
        for i, sk in enumerate(role_skills_norm)
        if sk and sk not in user_skills_norm
    ], survey_scores)

    graph_skills        = get_graph_skills()
    pathfindable_skills = [s for s in missing_skills if s in graph_skills]
    unsupported_skills  = [s for s in missing_skills if s not in graph_skills]
    scored_gaps         = score_skill_gaps(missing_skills, roles_catalog)
    role_total          = max(len(role_top_skills), 1)
    have_count          = role_total - len(missing_skills)
    match_score         = int(round((have_count / role_total) * 100))

    # ── Certifications ─────────────────────────────────
    role_category_tag = (role.get("category", "") or "").strip().lower()
    missing_norm      = {normalize_skill(s) for s in missing_skills}
    recommended_certs = []
    for cert in CERT_LIBRARY:
        cert_skill_norm = {normalize_skill(s) for s in cert["skills"]}
        covers_gap      = bool(missing_norm.intersection(cert_skill_norm))
        category_match  = role_category_tag in [t.lower() for t in cert.get("tags", [])]
        if covers_gap or category_match:
            covered = list(missing_norm.intersection(cert_skill_norm))
            reason  = (
                f"Helps you build: {', '.join(covered[:3])}." if covered
                else f"Recommended for {role.get('category','')} roles."
            )
            recommended_certs.append({
                "name": cert["name"], "provider": cert["provider"],
                "level": cert["level"], "skills": cert["skills"],
                "reason": reason, "link": cert.get("link", ""),
            })
    recommended_certs = recommended_certs[:4]

    # ── Dijkstra paths ─────────────────────────────────
    from data import courses as course_catalog
    course_lookup  = {c["name"]: c for c in course_catalog}
    optimize_for   = profile_data.get("optimize_for", "balanced")
    weight_presets = {
        "time":     {"weight_time": 0.8, "weight_difficulty": 0.1, "weight_cost": 0.1},
        "cost":     {"weight_time": 0.1, "weight_difficulty": 0.1, "weight_cost": 0.8},
        "balanced": {"weight_time": 0.4, "weight_difficulty": 0.3, "weight_cost": 0.3},
        "easy":     {"weight_time": 0.1, "weight_difficulty": 0.8, "weight_cost": 0.1},
    }
    weights        = weight_presets.get(optimize_for, weight_presets["balanced"])
    learning_paths = []
    for gap_skill in pathfindable_skills[:4]:
        path, cost = find_learning_path(graph, user_skills, gap_skill, **weights)
        if path and len(path) > 1:
            steps       = []
            graph_edges = []
            for i in range(len(path) - 1):
                edge        = graph.get_edge_data(path[i], path[i + 1])
                course_name = edge.get("course", "")
                edge_cost   = (
                    edge.get("time", 0) * weights["weight_time"]
                    + edge.get("difficulty", 0) * weights["weight_difficulty"]
                    + edge.get("cost", 0) * weights["weight_cost"]
                )
                graph_edges.append({
                    "from":       path[i],
                    "to":         path[i + 1],
                    "course":     course_name,
                    "time":       edge.get("time", 0),
                    "difficulty": edge.get("difficulty", 0),
                    "cost":       edge.get("cost", 0),
                    "edge_cost":  round(edge_cost, 1),
                    "is_hidden":  course_name == "return_to_root" or course_name.startswith("prereq_check::"),
                })
                if course_name == "return_to_root" or course_name.startswith("prereq_check::"):
                    continue
                course_data = course_lookup.get(course_name, {})
                video_query = f"{path[i + 1]} {course_name} beginner tutorial"
                videos      = fetch_youtube_videos(video_query, max_results=3)
                learn_query = f"{path[i + 1]} {course_name}"
                course_link = (
                    course_data.get("edx_link", "")
                    or course_data.get("ms_learn", "")
                    or microsoft_learn_search_url(learn_query)
                )
                steps.append({
                    "from":           path[i],
                    "to":             path[i + 1],
                    "course":         course_name,
                    "provider":       course_data.get("provider", ""),
                    "course_link":    course_link,
                    "edx_link":       course_data.get("edx_link", ""),
                    "ms_learn":       microsoft_learn_search_url(learn_query),
                    "ms_learn_search": microsoft_learn_search_url(learn_query),
                    "youtube_search": course_data.get("youtube", ""),
                    "topics":         course_data.get("topics", []),
                    "video_query":    video_query,
                    "videos":         videos,
                    "time":           edge.get("time", 0),
                    "difficulty":     edge.get("difficulty", 0),
                    "cost":           edge.get("cost", 0),
                    "edge_cost":      round(edge_cost, 1),
                    "why_this_step":  (
                        f"This course moves you from {path[i]} to {path[i + 1]} "
                        f"and was selected because it is on the lowest-cost route "
                        f"to {gap_skill} under your {optimize_for} preference."
                    ),
                })
            learning_paths.append({
                "target_skill": gap_skill,
                "path":         path,
                "graph_edges":  graph_edges,
                "steps":        steps,
                "total_cost":   round(cost, 1),
                "weights":      weights,
                "optimize_for": optimize_for,
            })

    recommended_learning = build_recommended_learning(learning_paths)

    # Videos now belong to ordered graph steps, not loose skill cards.
    skill_videos = {}

    # ── Job listings ───────────────────────────────────
    location   = profile_data.get("location", "Remote") or "Remote"
    role_title = role.get("title", "")
    job_listings = []
    try:
        from adapters.caribbeanjobs import fetch_jobs
        raw_jobs = fetch_jobs(role_title, location=location) or []
        job_listings = [
            {
                "title": job.get("title", role_title),
                "company": job.get("company", "CaribbeanJobs"),
                "location": job.get("location", location),
                "link": job.get("link") or job.get("url") or "",
                "skills": role_top_skills[:3],
                "source": "CaribbeanJobs",
            }
            for job in raw_jobs[:6]
        ]
    except Exception as e:
        print("CaribbeanJobs adapter error:", e)

    if not job_listings:
        encoded_role     = urllib.parse.quote(role_title)
        encoded_location = urllib.parse.quote(location)
        job_listings = [
            {
                "title":    f"{role_title} roles",
                "company":  "LinkedIn Jobs",
                "location": location,
                "link":     f"https://www.linkedin.com/jobs/search/?keywords={encoded_role}&location={encoded_location}",
                "skills":   role_top_skills[:3],
                "source":   "LinkedIn",
            },
            {
                "title":    f"{role_title} openings",
                "company":  "CaribbeanJobs",
                "location": location,
                "link":     f"https://www.caribbeanjobs.com/ShowResults.aspx?Keywords={encoded_role}",
                "skills":   role_top_skills[:3],
                "source":   "CaribbeanJobs",
            },
            {
                "title":    f"{role_title} listings",
                "company":  "Indeed Jamaica",
                "location": location,
                "link":     f"https://jm.indeed.com/jobs?q={encoded_role}&l={encoded_location}",
                "skills":   role_top_skills[:3],
                "source":   "Indeed",
            },
        ]

    # ── Progress checklist ────────────────────────────
    progress = get_progress(
        session.get("user_id"),
        profile_id=session.get("active_profile_id"),
        role_id=selected_role_id,
    )
    if not progress or progress.get("role_id") != selected_role_id:
        progress = {
            "role_id":   selected_role_id,
            "skills":    missing_skills,
            "completed": [],
        }
        progress = save_progress(
            session.get("user_id"),
            progress,
            profile_id=session.get("active_profile_id"),
        )
        session["progress"] = progress
    else:
        tracked_skills = list(progress.get("skills", []))
        tracked_norm = {normalize_skill(s) for s in tracked_skills}
        for s in missing_skills:
            if normalize_skill(s) not in tracked_norm:
                tracked_skills.append(s)
                tracked_norm.add(normalize_skill(s))

        progress["skills"] = tracked_skills
        progress["completed"] = [
            s for s in progress.get("completed", [])
            if normalize_skill(s) in tracked_norm
        ]
        progress = save_progress(
            session.get("user_id"),
            progress,
            profile_id=session.get("active_profile_id"),
        )
        session["progress"] = progress

    results_obj = {
        "degree":               profile_data.get("degree", ""),
        "location":             profile_data.get("location", ""),
        "user_skills":          user_skills,
        "selected_role":        role.get("title", ""),
        "top_skills_in_jobs":   role_top_skills,
        "missing_skills":       missing_skills,
        "scored_gaps":          scored_gaps,
        "match_score":          match_score,
        "recommended_certs":    recommended_certs,
        "recommended_learning": recommended_learning,
        "learning_paths":       learning_paths,
        "skill_videos":         skill_videos,
        "job_listings":         job_listings,
        "unsupported_skills":   unsupported_skills,
        "profile_skills":       profile_skills,
        "survey_scores":        survey_scores,
        "survey_summary":       survey_summary,
        "graph_overview":       build_graph_overview(graph),
    }
    results_obj["roadmap_steps"] = build_roadmap_steps(results_obj)
    return render_template("results.html", results=results_obj)


@app.route("/progress", methods=["GET", "POST"])
@login_required
def progress():
    profile_id = session.get("active_profile_id")
    selected_role_id = session.get("selected_role_id")
    data = get_progress(
        session.get("user_id"),
        profile_id=profile_id,
        role_id=selected_role_id,
    )
    if not data.get("skills") and session.get("progress"):
        data = session.get("progress", {"skills": [], "completed": []})

    if request.method == "POST":
        completed = request.form.getlist("completed")
        # Keep previously completed skills when the user saves new ones later.
        allowed = {normalize_skill(s) for s in data.get("skills", [])}
        merged_completed = list(data.get("completed", []))
        completed_norm = {normalize_skill(s) for s in merged_completed}
        for c in completed:
            c_norm = normalize_skill(c)
            if c_norm in allowed and c_norm not in completed_norm:
                merged_completed.append(c)
                completed_norm.add(c_norm)
        data["completed"] = [
            c for c in merged_completed
            if normalize_skill(c) in allowed
        ]
        if selected_role_id:
            data["role_id"] = selected_role_id
        data = save_progress(session.get("user_id"), data, profile_id=profile_id)
        session["progress"] = data

        # Also merge newly-completed skills into the profile so they
        # persist across sessions and show up in results immediately
        profile = get_latest_profile(session.get("user_id")) or session.get("profile", {})
        if profile:
            existing = {normalize_skill(s) for s in profile.get("skills", [])}
            for s in data["completed"]:
                if normalize_skill(s) not in existing:
                    profile.setdefault("skills", []).append(s)
                    existing.add(normalize_skill(s))
            saved_profile = save_profile(
                session.get("user_id"),
                profile,
                profile_id=profile.get("id") or profile_id,
            )
            if saved_profile:
                profile = saved_profile
                session["active_profile_id"] = saved_profile["id"]
            session["profile"] = profile
        return redirect(url_for("progress"))

    profiles = get_user_profiles(session.get("user_id"))
    return render_template("progress.html", progress=data, profiles=profiles)


@app.route("/survey", methods=["GET"])
@login_required
def survey():
    profile_data = get_latest_profile(session.get("user_id")) or session.get("profile")
    if profile_data:
        session["profile"] = profile_data
        session["active_profile_id"] = profile_data.get("id")
    if not profile_data:
        return redirect(url_for("profile"))

    selected_role_id = session.get("selected_role_id")
    role             = find_role_by_id(selected_role_id, load_roles()) if selected_role_id else None
    if not role:
        return redirect(url_for("roles"))

    questions, survey_meta, gaps = build_dynamic_survey_questions(profile_data, role)

    print("Survey claimed role skills:", survey_meta["claimed_target_count"])
    print("Survey gaps found:", gaps)
    print("Survey questions generated:", survey_meta["total"])

    session["survey_gaps"] = gaps
    session["survey_questions"] = questions
    return render_template(
        "survey.html",
        questions=questions,
        survey_meta=survey_meta,
        role=role,
        profile=profile_data,
    )


@app.route("/survey/submit", methods=["POST"])
@login_required
def survey_submit():
    profile_data = get_latest_profile(session.get("user_id")) or session.get("profile", {})
    questions = session.get("survey_questions", [])
    survey_scores = []

    for key, answer in request.form.items():
        if not key.startswith("answer_"):
            continue
        index = key.replace("answer_", "", 1)
        if not index.isdigit():
            continue
        q_index = int(index)
        expected = questions[q_index].get("answer") if q_index < len(questions) else None
        skill = request.form.get(f"skill_{index}", "").strip()
        reason = request.form.get(f"reason_{index}", "").strip()
        if skill:
            is_correct = bool(expected and answer == expected)
            if reason == "validate_claimed" and is_correct:
                status = "confirmed"
            elif reason == "validate_claimed":
                status = "needs_review"
            elif is_correct:
                status = "familiarity_shown"
            else:
                status = "learning_gap"

            survey_scores.append({
                "skill": skill,
                "reason": reason,
                "answer": answer,
                "correct_answer": expected,
                "is_correct": is_correct,
                "explanation": questions[q_index].get("explanation", "") if q_index < len(questions) else "",
                "status": status,
            })

    correct_count = sum(1 for item in survey_scores if item["is_correct"])
    total_count = len(survey_scores)
    survey_summary = {
        "total": total_count,
        "correct": correct_count,
        "percent": int(round((correct_count / total_count) * 100)) if total_count else 0,
        "confirmed": sum(1 for item in survey_scores if item["status"] == "confirmed"),
        "needs_review": sum(1 for item in survey_scores if item["status"] == "needs_review"),
        "familiarity_shown": sum(1 for item in survey_scores if item["status"] == "familiarity_shown"),
        "learning_gap": sum(1 for item in survey_scores if item["status"] == "learning_gap"),
    }

    session["survey_scores"] = survey_scores
    session["survey_summary"] = survey_summary
    session["profile"] = profile_data

    return redirect(url_for("survey_results"))


@app.get("/survey/results")
@login_required
def survey_results():
    survey_scores = session.get("survey_scores", [])
    survey_summary = session.get("survey_summary", {})
    if not survey_scores:
        return redirect(url_for("survey"))
    return render_template(
        "survey_results.html",
        survey_scores=survey_scores,
        survey_summary=survey_summary,
    )


@app.route("/set-usertype", methods=["POST"])
def set_usertype():
    session["user_type"] = request.form.get("user_type", "student")
    return redirect(url_for("roles"))


@app.get("/reset")
def reset():
    # Only clear pathway data, keep the user logged in
    session.pop("profile", None)
    session.pop("selected_role_id", None)
    session.pop("progress", None)
    session.pop("survey_gaps", None)
    session.pop("survey_scores", None)
    session.pop("survey_summary", None)
    session.pop("survey_questions", None)
    session.pop("flash", None)
    session.pop("resume_notice", None)
    return redirect(url_for("roles"))


@app.get("/loading")
def loading():
    return render_template("loading.html")


# ── Firebase session bridge ───────────────────────────────────
@app.post("/set-session")
def set_session():
    data = request.get_json(silent=True) or {}
    user = upsert_user(
        data.get("user_id"),
        display_name=data.get("display_name"),
        email=data.get("email"),
        username=data.get("username"),
        user_type=data.get("user_type"),
    )

    display_name = (
        (user or {}).get("display_name")
        or data.get("display_name")
        or data.get("email")
    )

    session["user_id"]      = data.get("user_id")
    session["display_name"] = display_name

    existing_profile = get_latest_profile(data.get("user_id"))
    if existing_profile:
        session["profile"] = existing_profile
        session["active_profile_id"] = existing_profile["id"]

    selected_role_id = session.get("selected_role_id")
    existing_progress = get_progress(
        data.get("user_id"),
        profile_id=session.get("active_profile_id"),
        role_id=selected_role_id,
    )
    if existing_progress.get("skills"):
        session["progress"] = existing_progress

    if user:
        session["db_user_id"] = user["id"]
    return {
        "ok": True,
        "display_name": display_name,
        "email": (user or {}).get("email") or data.get("email"),
    }

@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.get("/debug-session")
def debug_session():
    return jsonify({
        "user_id":      session.get("user_id"),
        "display_name": session.get("display_name"),
        "has_profile":  bool(session.get("profile")),
    })


if __name__ == "__main__":
    app.run(debug=True)
