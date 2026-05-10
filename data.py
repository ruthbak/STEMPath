"""
data.py
=======
STEMPath course and resource catalog used to build the Dijkstra skill graph.

This module defines two data structures:

skills (list[str])
    The canonical set of skill names recognised by the STEMPath system.
    These match the skill names produced by import_onet_roles.py when
    mapping O*NET technology examples to internal skill identifiers.

courses (list[dict])
    The full catalog of learning resources — including YouTube intro videos,
    Khan Academy reinforcement videos, structured online courses, and
    certification prep materials — used by graph_builder.py to construct
    the directed weighted skill graph.

Graph node structure
--------------------
Each course entry teaches one or more skills and may require prerequisite
skills. build_learning_graph() in graph_builder.py uses these relationships
to wire up three types of graph edges:

    No prerequisites  : ROOT → taught_skill
    One prerequisite  : prereq → taught_skill
    Multi-prerequisite: prereq_1, prereq_2 → GATE::course → taught_skill

Resource types
--------------
Each course entry includes a resource_type field that classifies the
learning resource, used by the results route in app.py to select the
appropriate YouTube search query when fetching embedded videos:

    "video"  — Short YouTube or Khan Academy intro (time: 1–6 hrs, cost: 0)
               Designed as a lightweight first step before a full course.
    "course" — Structured online course from Coursera, edX, GitHub etc.
               Provides the primary skill certification or qualification.

Learning path pattern
---------------------
Each skill follows a consistent 2–3 step learning path in the graph:

    Step 1: YouTube intro video  (free, fast, low difficulty)
    Step 2: Khan Academy video   (free, reinforcement — some skills only)
    Step 3: Structured course    (primary qualification, may have cost)

This pattern ensures Dijkstra's algorithm always finds a graduated,
resource-appropriate path rather than jumping directly to advanced material.

Extending the catalog
---------------------
To add support for a new skill:
    1. Add the skill name to the skills list.
    2. Add a YouTube intro entry (no prerequisites, resource_type="video").
    3. Add a structured course entry (prereq = the intro skill taught above).
    4. Restart the Flask app — the graph is rebuilt from this file at startup.

Fields per course entry
-----------------------
    name          (str)   : Unique identifier used as graph edge label.
    teaches       (list)  : Skill node(s) this resource unlocks in the graph.
    prerequisites (list)  : Skill node(s) required before this can be taken.
    time          (int)   : Estimated hours to complete.
    difficulty    (int)   : 1 = beginner, 2 = intermediate, 3 = advanced.
    cost          (float) : Monetary cost in USD (0 = free).
    provider      (str)   : Platform or institution offering the resource.
    resource_type (str)   : "video" or "course" — used for YouTube fetching.
    youtube_query (str)   : Search query used by fetch_youtube_videos()
                            when this node appears in a Dijkstra path.
    youtube       (str)   : Fallback YouTube search URL (used in template).
    ms_learn      (str)   : Primary course link (Microsoft Learn, Coursera,
                            edX, or other provider URL).
"""


# ── Canonical skill list ──────────────────────────────────────
# These names must match the internal skill identifiers produced by
# import_onet_roles.py (via INTERNAL_SKILL_KEYWORDS mapping).
skills = [
    "Python", "SQL", "Statistics", "Machine Learning",
    "Data Visualization", "Networking", "Linux",
    "Security Basics", "Cloud", "Git", "APIs", "TensorFlow",
    "JavaScript", "HTML", "CSS", "Java",
]

courses = [

    # ══════════════════════════════════════════════════════════
    # PYTHON
    # ══════════════════════════════════════════════════════════

    # Step 1 — YouTube intro (free, fast, easy entry point)
    {
        "name": "Python Intro (YouTube)",
        "teaches": ["Python Basics"],
        "prerequisites": [],
        "time": 3,
        "difficulty": 1,
        "cost": 0,
        "provider": "YouTube",
        "resource_type": "video",
        "youtube_query": "Python for beginners full course",
        "youtube": "https://www.youtube.com/results?search_query=python+for+beginners+full+course",
        "ms_learn": "",
    },

    # Step 2 — Khan Academy reinforcement
    {
        "name": "Intro to Python (Khan Academy)",
        "teaches": ["Python Basics"],
        "prerequisites": ["Python Basics"],
        "time": 5,
        "difficulty": 1,
        "cost": 0,
        "provider": "Khan Academy",
        "resource_type": "video",
        "youtube_query": "Khan Academy intro to programming Python",
        "youtube": "https://www.youtube.com/results?search_query=khan+academy+intro+to+programming+python",
        "ms_learn": "",
    },

    # Step 3 — Full structured course
    {
        "name": "Python for Everybody",
        "teaches": ["Python"],
        "prerequisites": ["Python Basics"],
        "time": 30,
        "difficulty": 1,
        "cost": 0,
        "provider": "Coursera",
        "topics": ["Syntax and variables", "Control flow", "Functions", "Files and data structures"],
        "resource_type": "course",
        "ms_learn": "https://learn.microsoft.com/en-us/training/paths/beginner-python/",
        "youtube": "https://www.youtube.com/results?search_query=python+for+everybody+coursera",
    },

    # ══════════════════════════════════════════════════════════
    # SQL
    # ══════════════════════════════════════════════════════════

    {
        "name": "SQL Intro (YouTube)",
        "teaches": ["SQL Basics"],
        "prerequisites": [],
        "time": 2,
        "difficulty": 1,
        "cost": 0,
        "provider": "YouTube",
        "resource_type": "video",
        "youtube_query": "SQL for beginners tutorial",
        "youtube": "https://www.youtube.com/results?search_query=sql+for+beginners+tutorial",
        "ms_learn": "",
    },

    {
        "name": "Intro to SQL (Khan Academy)",
        "teaches": ["SQL Basics"],
        "prerequisites": ["SQL Basics"],
        "time": 4,
        "difficulty": 1,
        "cost": 0,
        "provider": "Khan Academy",
        "resource_type": "video",
        "youtube_query": "Khan Academy intro to SQL",
        "youtube": "https://www.youtube.com/results?search_query=khan+academy+intro+to+sql",
        "ms_learn": "",
    },

    {
        "name": "SQL Fundamentals",
        "teaches": ["SQL"],
        "prerequisites": ["SQL Basics"],
        "time": 20,
        "difficulty": 1,
        "cost": 0,
        "provider": "edX",
        "topics": ["Tables and relationships", "SELECT queries", "Filtering and sorting", "Joins and aggregates"],
        "resource_type": "course",
        "ms_learn": "https://learn.microsoft.com/en-us/training/paths/get-started-querying-with-transact-sql/",
        "youtube": "https://www.youtube.com/results?search_query=sql+fundamentals+full+course",
    },

    # ══════════════════════════════════════════════════════════
    # STATISTICS
    # ══════════════════════════════════════════════════════════

    {
        "name": "Statistics Intro (YouTube)",
        "teaches": ["Statistics Basics"],
        "prerequisites": [],
        "time": 3,
        "difficulty": 1,
        "cost": 0,
        "provider": "YouTube",
        "resource_type": "video",
        "youtube_query": "statistics for beginners full course",
        "youtube": "https://www.youtube.com/results?search_query=statistics+for+beginners+full+course",
        "ms_learn": "",
    },

    {
        "name": "Statistics (Khan Academy)",
        "teaches": ["Statistics Basics"],
        "prerequisites": ["Statistics Basics"],
        "time": 6,
        "difficulty": 1,
        "cost": 0,
        "provider": "Khan Academy",
        "resource_type": "video",
        "youtube_query": "Khan Academy statistics and probability",
        "youtube": "https://www.youtube.com/results?search_query=khan+academy+statistics+and+probability",
        "ms_learn": "",
    },

    {
        "name": "Intro to Statistics",
        "teaches": ["Statistics"],
        "prerequisites": ["Python", "Statistics Basics"],
        "time": 40,
        "difficulty": 2,
        "cost": 0,
        "provider": "edX",
        "resource_type": "course",
        "ms_learn": "https://learn.microsoft.com/en-us/training/paths/data-science-know-your-data/",
        "youtube": "https://www.youtube.com/results?search_query=statistics+for+data+science+full+course",
    },

    {
        "name": "Statistics for Data Science",
        "teaches": ["Statistics"],
        "prerequisites": ["Statistics Basics"],
        "time": 35,
        "difficulty": 2,
        "cost": 0,
        "provider": "Coursera",
        "resource_type": "course",
        "topics": ["Descriptive statistics", "Probability", "Distributions", "Hypothesis testing"],
        "ms_learn": "https://learn.microsoft.com/en-us/training/paths/data-science-know-your-data/",
        "youtube": "https://www.youtube.com/results?search_query=statistics+for+data+science+beginners",
    },

    # ══════════════════════════════════════════════════════════
    # DATA VISUALIZATION
    # ══════════════════════════════════════════════════════════

    {
        "name": "Data Visualization Intro (YouTube)",
        "teaches": ["Data Visualization Basics"],
        "prerequisites": ["Python"],
        "time": 2,
        "difficulty": 1,
        "cost": 0,
        "provider": "YouTube",
        "resource_type": "video",
        "youtube_query": "data visualization Python matplotlib seaborn tutorial",
        "youtube": "https://www.youtube.com/results?search_query=data+visualization+python+matplotlib+seaborn",
        "ms_learn": "",
    },

    {
        "name": "Data Analysis with Python",
        "teaches": ["Data Visualization"],
        "prerequisites": ["Python", "SQL", "Data Visualization Basics"],
        "time": 40,
        "difficulty": 2,
        "cost": 0,
        "provider": "Coursera",
        "topics": ["Pandas dataframes", "Cleaning datasets", "Exploratory analysis", "Charts and dashboards"],
        "resource_type": "course",
        "ms_learn": "https://learn.microsoft.com/en-us/training/paths/visualize-data-power-bi/",
        "youtube": "https://www.youtube.com/results?search_query=data+analysis+python+pandas+matplotlib+full+course",
    },

    # ══════════════════════════════════════════════════════════
    # MACHINE LEARNING
    # ══════════════════════════════════════════════════════════

    {
        "name": "Machine Learning Intro (YouTube)",
        "teaches": ["ML Basics"],
        "prerequisites": ["Python", "Statistics"],
        "time": 3,
        "difficulty": 2,
        "cost": 0,
        "provider": "YouTube",
        "resource_type": "video",
        "youtube_query": "machine learning explained for beginners",
        "youtube": "https://www.youtube.com/results?search_query=machine+learning+explained+beginners",
        "ms_learn": "",
    },

    {
        "name": "ML Basics",
        "teaches": ["Machine Learning"],
        "prerequisites": ["Python", "Statistics", "ML Basics"],
        "time": 60,
        "difficulty": 3,
        "cost": 49,
        "provider": "edX",
        "topics": ["Supervised learning", "Model training", "Evaluation metrics", "Overfitting and validation"],
        "resource_type": "course",
        "ms_learn": "https://learn.microsoft.com/en-us/training/paths/introduction-machine-learning/",
        "youtube": "https://www.youtube.com/results?search_query=machine+learning+full+course+beginners",
    },

    # ══════════════════════════════════════════════════════════
    # TENSORFLOW
    # ══════════════════════════════════════════════════════════

    {
        "name": "TensorFlow Intro (YouTube)",
        "teaches": ["TF Basics"],
        "prerequisites": ["Machine Learning"],
        "time": 2,
        "difficulty": 2,
        "cost": 0,
        "provider": "YouTube",
        "resource_type": "video",
        "youtube_query": "TensorFlow tutorial for beginners",
        "youtube": "https://www.youtube.com/results?search_query=tensorflow+tutorial+beginners",
        "ms_learn": "",
    },

    {
        "name": "TensorFlow Fundamentals",
        "teaches": ["TensorFlow"],
        "prerequisites": ["Machine Learning", "TF Basics"],
        "time": 50,
        "difficulty": 3,
        "cost": 0,
        "provider": "Google",
        "topics": ["Tensors", "Neural network layers", "Training loops", "Model evaluation"],
        "resource_type": "course",
        "ms_learn": "https://learn.microsoft.com/en-us/training/paths/introduction-machine-learning/",
        "youtube": "https://www.youtube.com/results?search_query=tensorflow+full+course+beginners",
    },

    # ══════════════════════════════════════════════════════════
    # NETWORKING
    # ══════════════════════════════════════════════════════════

    {
        "name": "Networking Intro (YouTube)",
        "teaches": ["Networking Basics"],
        "prerequisites": [],
        "time": 2,
        "difficulty": 1,
        "cost": 0,
        "provider": "YouTube",
        "resource_type": "video",
        "youtube_query": "computer networking fundamentals for beginners",
        "youtube": "https://www.youtube.com/results?search_query=computer+networking+fundamentals+beginners",
        "ms_learn": "",
    },

    {
        "name": "Networking Fundamentals",
        "teaches": ["Networking"],
        "prerequisites": ["Networking Basics"],
        "time": 35,
        "difficulty": 2,
        "cost": 0,
        "provider": "Cisco NetAcad",
        "topics": ["IP addressing", "Routing basics", "Switching basics", "Network troubleshooting"],
        "resource_type": "course",
        "ms_learn": "https://learn.microsoft.com/en-us/training/paths/implement-windows-server-networking/",
        "youtube": "https://www.youtube.com/results?search_query=networking+fundamentals+full+course",
    },

    # ══════════════════════════════════════════════════════════
    # LINUX
    # ══════════════════════════════════════════════════════════

    {
        "name": "Linux Intro (YouTube)",
        "teaches": ["Linux Basics"],
        "prerequisites": [],
        "time": 2,
        "difficulty": 1,
        "cost": 0,
        "provider": "YouTube",
        "resource_type": "video",
        "youtube_query": "Linux command line for beginners tutorial",
        "youtube": "https://www.youtube.com/results?search_query=linux+command+line+beginners+tutorial",
        "ms_learn": "",
    },

    {
        "name": "Linux Command Line Basics",
        "teaches": ["Linux"],
        "prerequisites": ["Linux Basics"],
        "time": 15,
        "difficulty": 1,
        "cost": 0,
        "provider": "edX",
        "topics": ["Terminal navigation", "Files and directories", "Permissions", "Package management", "Shell basics"],
        "resource_type": "course",
        "ms_learn": "https://learn.microsoft.com/en-us/training/paths/azure-linux/",
        "youtube": "https://www.youtube.com/results?search_query=linux+command+line+full+course+beginners",
    },

    # ══════════════════════════════════════════════════════════
    # SECURITY
    # ══════════════════════════════════════════════════════════

    {
        "name": "Cybersecurity Intro (YouTube)",
        "teaches": ["Security Intro"],
        "prerequisites": ["Networking"],
        "time": 2,
        "difficulty": 2,
        "cost": 0,
        "provider": "YouTube",
        "resource_type": "video",
        "youtube_query": "cybersecurity for beginners full course",
        "youtube": "https://www.youtube.com/results?search_query=cybersecurity+for+beginners+full+course",
        "ms_learn": "",
    },

    {
        "name": "CompTIA Security+ Prep",
        "teaches": ["Security Basics"],
        "prerequisites": ["Networking", "Security Intro"],
        "time": 60,
        "difficulty": 3,
        "cost": 30,
        "provider": "CompTIA",
        "topics": ["Threats and vulnerabilities", "Identity and access", "Network security", "Incident response"],
        "resource_type": "course",
        "ms_learn": "https://learn.microsoft.com/en-us/training/paths/security-compliance-identity-fundamentals/",
        "youtube": "https://www.youtube.com/results?search_query=comptia+security+plus+full+course",
    },

    # ══════════════════════════════════════════════════════════
    # CLOUD
    # ══════════════════════════════════════════════════════════

    {
        "name": "Cloud Computing Intro (YouTube)",
        "teaches": ["Cloud Basics"],
        "prerequisites": ["Networking"],
        "time": 2,
        "difficulty": 1,
        "cost": 0,
        "provider": "YouTube",
        "resource_type": "video",
        "youtube_query": "cloud computing explained for beginners",
        "youtube": "https://www.youtube.com/results?search_query=cloud+computing+explained+beginners",
        "ms_learn": "",
    },

    {
        "name": "AWS Cloud Practitioner",
        "teaches": ["Cloud"],
        "prerequisites": ["Networking", "Cloud Basics"],
        "time": 30,
        "difficulty": 2,
        "cost": 0,
        "provider": "AWS / Microsoft Learn",
        "topics": ["Cloud concepts", "Compute and storage", "Networking in cloud", "Pricing and governance"],
        "resource_type": "course",
        "ms_learn": "https://learn.microsoft.com/en-us/training/paths/az-900-describe-cloud-concepts/",
        "youtube": "https://www.youtube.com/results?search_query=aws+cloud+practitioner+full+course",
    },

    # ══════════════════════════════════════════════════════════
    # GIT
    # ══════════════════════════════════════════════════════════

    {
        "name": "Git Intro (YouTube)",
        "teaches": ["Git Basics"],
        "prerequisites": [],
        "time": 1,
        "difficulty": 1,
        "cost": 0,
        "provider": "YouTube",
        "resource_type": "video",
        "youtube_query": "Git and GitHub for beginners crash course",
        "youtube": "https://www.youtube.com/results?search_query=git+github+beginners+crash+course",
        "ms_learn": "",
    },

    {
        "name": "Git & GitHub for Beginners",
        "teaches": ["Git"],
        "prerequisites": ["Git Basics"],
        "time": 10,
        "difficulty": 1,
        "cost": 0,
        "provider": "GitHub",
        "topics": ["Repositories", "Commits", "Branches", "Pull requests"],
        "resource_type": "course",
        "ms_learn": "https://learn.microsoft.com/en-us/training/paths/intro-to-vc-git/",
        "youtube": "https://www.youtube.com/results?search_query=git+github+full+course+beginners",
    },

    # ══════════════════════════════════════════════════════════
    # APIs
    # ══════════════════════════════════════════════════════════

    {
        "name": "APIs Intro (YouTube)",
        "teaches": ["API Basics"],
        "prerequisites": ["Python"],
        "time": 1,
        "difficulty": 1,
        "cost": 0,
        "provider": "YouTube",
        "resource_type": "video",
        "youtube_query": "what is an API explained for beginners",
        "youtube": "https://www.youtube.com/results?search_query=what+is+api+explained+beginners",
        "ms_learn": "",
    },

    {
        "name": "REST API Development",
        "teaches": ["APIs"],
        "prerequisites": ["Python", "API Basics"],
        "time": 25,
        "difficulty": 2,
        "cost": 0,
        "provider": "edX",
        "topics": ["HTTP basics", "Routes and endpoints", "JSON payloads", "Authentication basics"],
        "resource_type": "course",
        "ms_learn": "https://learn.microsoft.com/en-us/training/paths/build-serverless-full-stack-apps-azure/",
        "youtube": "https://www.youtube.com/results?search_query=rest+api+development+python+full+course",
    },

    # ══════════════════════════════════════════════════════════
    # HTML / CSS
    # ══════════════════════════════════════════════════════════

    {
        "name": "HTML & CSS Intro (YouTube)",
        "teaches": ["Web Basics"],
        "prerequisites": [],
        "time": 2,
        "difficulty": 1,
        "cost": 0,
        "provider": "YouTube",
        "resource_type": "video",
        "youtube_query": "HTML CSS for beginners full course",
        "youtube": "https://www.youtube.com/results?search_query=html+css+beginners+full+course",
        "ms_learn": "",
    },

    {
        "name": "HTML & CSS Fundamentals",
        "teaches": ["CSS", "HTML"],
        "prerequisites": ["Web Basics"],
        "time": 15,
        "difficulty": 1,
        "cost": 0,
        "provider": "MDN / freeCodeCamp",
        "topics": ["HTML structure", "CSS selectors", "Layout", "Responsive design"],
        "resource_type": "course",
        "ms_learn": "https://learn.microsoft.com/en-us/training/paths/web-development-101/",
        "youtube": "https://www.youtube.com/results?search_query=html+css+full+course+beginners",
    },

    # ══════════════════════════════════════════════════════════
    # JAVASCRIPT
    # ══════════════════════════════════════════════════════════

    {
        "name": "JavaScript Intro (YouTube)",
        "teaches": ["JS Basics"],
        "prerequisites": ["HTML", "CSS"],
        "time": 2,
        "difficulty": 1,
        "cost": 0,
        "provider": "YouTube",
        "resource_type": "video",
        "youtube_query": "JavaScript for beginners full course",
        "youtube": "https://www.youtube.com/results?search_query=javascript+for+beginners+full+course",
        "ms_learn": "",
    },

    {
        "name": "JavaScript Basics",
        "teaches": ["JavaScript"],
        "prerequisites": ["HTML", "CSS", "JS Basics"],
        "time": 30,
        "difficulty": 2,
        "cost": 0,
        "provider": "freeCodeCamp",
        "topics": ["Variables and functions", "DOM manipulation", "Events", "Fetch and async basics"],
        "resource_type": "course",
        "ms_learn": "https://learn.microsoft.com/en-us/training/paths/web-development-101/",
        "youtube": "https://www.youtube.com/results?search_query=javascript+full+course+beginners",
    },

    # ══════════════════════════════════════════════════════════
    # JAVA
    # ══════════════════════════════════════════════════════════

    {
        "name": "Java Intro (YouTube)",
        "teaches": ["Java Basics"],
        "prerequisites": [],
        "time": 2,
        "difficulty": 1,
        "cost": 0,
        "provider": "YouTube",
        "resource_type": "video",
        "youtube_query": "Java programming for beginners full course",
        "youtube": "https://www.youtube.com/results?search_query=java+programming+for+beginners+full+course",
        "ms_learn": "",
    },

    {
        "name": "Java Programming Fundamentals",
        "teaches": ["Java"],
        "prerequisites": ["Java Basics"],
        "time": 40,
        "difficulty": 2,
        "cost": 0,
        "provider": "edX",
        "topics": ["Classes and objects", "Control flow", "Collections", "Error handling"],
        "resource_type": "course",
        "ms_learn": "https://learn.microsoft.com/en-us/training/paths/java-se-fundamentals/",
        "youtube": "https://www.youtube.com/results?search_query=java+programming+full+course+beginners",
    },
    # ══════════════════════════════════════════════════════════
    # MATLAB
    # ══════════════════════════════════════════════════════════
    {
        "name": "MATLAB Intro (YouTube)",
        "teaches": ["MATLAB"],
        "prerequisites": [],
        "time": 2, "difficulty": 1, "cost": 0,
        "provider": "YouTube", "resource_type": "video",
        "youtube_query": "MATLAB tutorial for beginners",
        "youtube": "https://www.youtube.com/results?search_query=matlab+tutorial+beginners",
        "ms_learn": "",
    },
    {
        "name": "MATLAB Fundamentals",
        "teaches": ["MATLAB"],
        "prerequisites": ["MATLAB"],
        "time": 20, "difficulty": 2, "cost": 0,
        "provider": "MathWorks", "resource_type": "course",
        "ms_learn": "https://www.mathworks.com/learn/training/matlab-fundamentals.html",
        "youtube": "https://www.youtube.com/results?search_query=matlab+fundamentals+course",
    },

    # ══════════════════════════════════════════════════════════
    # MEDICAL IMAGING
    # ══════════════════════════════════════════════════════════
    {
        "name": "Medical Imaging Intro (YouTube)",
        "teaches": ["Medical Imaging"],
        "prerequisites": [],
        "time": 2, "difficulty": 2, "cost": 0,
        "provider": "YouTube", "resource_type": "video",
        "youtube_query": "medical imaging fundamentals tutorial",
        "youtube": "https://www.youtube.com/results?search_query=medical+imaging+fundamentals+tutorial",
        "ms_learn": "",
    },
    {
        "name": "Medical Imaging Fundamentals",
        "teaches": ["Medical Imaging"],
        "prerequisites": ["Medical Imaging"],
        "time": 30, "difficulty": 3, "cost": 0,
        "provider": "edX", "resource_type": "course",
        "ms_learn": "https://www.edx.org/learn/medical-imaging",
        "youtube": "https://www.youtube.com/results?search_query=medical+imaging+full+course",
    },

    # ══════════════════════════════════════════════════════════
    # RESEARCH METHODS
    # ══════════════════════════════════════════════════════════
    {
        "name": "Research Methods Intro (YouTube)",
        "teaches": ["Research Methods"],
        "prerequisites": [],
        "time": 2, "difficulty": 1, "cost": 0,
        "provider": "YouTube", "resource_type": "video",
        "youtube_query": "research methods for beginners tutorial",
        "youtube": "https://www.youtube.com/results?search_query=research+methods+beginners",
        "ms_learn": "",
    },
    {
        "name": "Research Methods",
        "teaches": ["Research Methods"],
        "prerequisites": ["Research Methods"],
        "time": 20, "difficulty": 2, "cost": 0,
        "provider": "Coursera", "resource_type": "course",
        "ms_learn": "https://www.coursera.org/learn/research-methods",
        "youtube": "https://www.youtube.com/results?search_query=research+methods+full+course",
    },

    # ══════════════════════════════════════════════════════════
    # AUTOCAD
    # ══════════════════════════════════════════════════════════
    {
        "name": "AutoCAD Intro (YouTube)",
        "teaches": ["AutoCAD"],
        "prerequisites": [],
        "time": 2, "difficulty": 1, "cost": 0,
        "provider": "YouTube", "resource_type": "video",
        "youtube_query": "AutoCAD tutorial for beginners",
        "youtube": "https://www.youtube.com/results?search_query=autocad+tutorial+beginners",
        "ms_learn": "",
    },
    {
        "name": "AutoCAD Fundamentals",
        "teaches": ["AutoCAD"],
        "prerequisites": ["AutoCAD"],
        "time": 25, "difficulty": 2, "cost": 0,
        "provider": "Autodesk", "resource_type": "course",
        "ms_learn": "https://www.autodesk.com/certification/all-certifications/autocad",
        "youtube": "https://www.youtube.com/results?search_query=autocad+full+course",
    },

    # ══════════════════════════════════════════════════════════
    # RADIATION PHYSICS
    # ══════════════════════════════════════════════════════════
    {
        "name": "Radiation Physics Intro (YouTube)",
        "teaches": ["Radiation Physics"],
        "prerequisites": [],
        "time": 2, "difficulty": 2, "cost": 0,
        "provider": "YouTube", "resource_type": "video",
        "youtube_query": "radiation physics for beginners tutorial",
        "youtube": "https://www.youtube.com/results?search_query=radiation+physics+beginners",
        "ms_learn": "",
    },
    {
        "name": "Radiation Physics Fundamentals",
        "teaches": ["Radiation Physics"],
        "prerequisites": ["Radiation Physics"],
        "time": 35, "difficulty": 3, "cost": 0,
        "provider": "IAEA", "resource_type": "course",
        "ms_learn": "https://www.iaea.org/resources/rpop",
        "youtube": "https://www.youtube.com/results?search_query=radiation+physics+full+course",
    },

    # ══════════════════════════════════════════════════════════
    # STATISTICS (extended for non-CS roles)
    # ══════════════════════════════════════════════════════════
    {
        "name": "Statistical Analysis Intro (YouTube)",
        "teaches": ["Statistical Analysis"],
        "prerequisites": [],
        "time": 2, "difficulty": 1, "cost": 0,
        "provider": "YouTube", "resource_type": "video",
        "youtube_query": "statistical analysis for beginners tutorial",
        "youtube": "https://www.youtube.com/results?search_query=statistical+analysis+beginners",
        "ms_learn": "",
    },
    {
        "name": "Statistical Analysis",
        "teaches": ["Statistical Analysis"],
        "prerequisites": ["Statistical Analysis"],
        "time": 25, "difficulty": 2, "cost": 0,
        "provider": "Coursera", "resource_type": "course",
        "ms_learn": "https://www.coursera.org/learn/statistical-inference",
        "youtube": "https://www.youtube.com/results?search_query=statistical+analysis+full+course",
    },

    # ══════════════════════════════════════════════════════════
    # COMMUNICATION / SOFT SKILLS
    # ══════════════════════════════════════════════════════════
    {
        "name": "Communication Skills (YouTube)",
        "teaches": ["Communication"],
        "prerequisites": [],
        "time": 1, "difficulty": 1, "cost": 0,
        "provider": "YouTube", "resource_type": "video",
        "youtube_query": "professional communication skills for STEM students",
        "youtube": "https://www.youtube.com/results?search_query=professional+communication+skills+stem",
        "ms_learn": "",
    },
    {
        "name": "Technical Communication",
        "teaches": ["Communication"],
        "prerequisites": ["Communication"],
        "time": 15, "difficulty": 1, "cost": 0,
        "provider": "Coursera", "resource_type": "course",
        "ms_learn": "https://www.coursera.org/learn/technical-writing",
        "youtube": "https://www.youtube.com/results?search_query=technical+communication+course",
    },

    # ══════════════════════════════════════════════════════════
    # DATA ANALYSIS (general — covers many roles)
    # ══════════════════════════════════════════════════════════
    {
        "name": "Data Analysis Intro (YouTube)",
        "teaches": ["Data Analysis"],
        "prerequisites": [],
        "time": 2, "difficulty": 1, "cost": 0,
        "provider": "YouTube", "resource_type": "video",
        "youtube_query": "data analysis for beginners tutorial",
        "youtube": "https://www.youtube.com/results?search_query=data+analysis+beginners+tutorial",
        "ms_learn": "",
    },
    {
        "name": "Data Analysis Fundamentals",
        "teaches": ["Data Analysis"],
        "prerequisites": ["Data Analysis"],
        "time": 20, "difficulty": 2, "cost": 0,
        "provider": "IBM / Coursera", "resource_type": "course",
        "ms_learn": "https://www.coursera.org/professional-certificates/ibm-data-analyst",
        "youtube": "https://www.youtube.com/results?search_query=data+analysis+full+course",
    },

    # ══════════════════════════════════════════════════════════
    # PROJECT MANAGEMENT
    # ══════════════════════════════════════════════════════════
    {
        "name": "Project Management Intro (YouTube)",
        "teaches": ["Project Management"],
        "prerequisites": [],
        "time": 1, "difficulty": 1, "cost": 0,
        "provider": "YouTube", "resource_type": "video",
        "youtube_query": "project management for beginners tutorial",
        "youtube": "https://www.youtube.com/results?search_query=project+management+beginners",
        "ms_learn": "",
    },
    {
        "name": "Project Management Fundamentals",
        "teaches": ["Project Management"],
        "prerequisites": ["Project Management"],
        "time": 20, "difficulty": 2, "cost": 0,
        "provider": "Coursera / Google", "resource_type": "course",
        "ms_learn": "https://www.coursera.org/professional-certificates/google-project-management",
        "youtube": "https://www.youtube.com/results?search_query=project+management+full+course",
    },

    # ══════════════════════════════════════════════════════════
    # RESEARCH
    # ══════════════════════════════════════════════════════════
    {
        "name": "Research Skills Intro (YouTube)",
        "teaches": ["Research"],
        "prerequisites": [],
        "time": 2, "difficulty": 1, "cost": 0,
        "provider": "YouTube", "resource_type": "video",
        "youtube_query": "research skills for STEM students tutorial",
        "youtube": "https://www.youtube.com/results?search_query=research+skills+stem+students",
        "ms_learn": "",
    },
    {
        "name": "Research Methods and Skills",
        "teaches": ["Research"],
        "prerequisites": ["Research"],
        "time": 20, "difficulty": 2, "cost": 0,
        "provider": "Coursera", "resource_type": "course",
        "ms_learn": "https://www.coursera.org/learn/research-methods",
        "youtube": "https://www.youtube.com/results?search_query=research+methods+full+course",
    },

    # ══════════════════════════════════════════════════════════
    # EXCEL
    # ══════════════════════════════════════════════════════════
    {
        "name": "Excel Intro (YouTube)",
        "teaches": ["Excel"],
        "prerequisites": [],
        "time": 2, "difficulty": 1, "cost": 0,
        "provider": "YouTube", "resource_type": "video",
        "youtube_query": "Microsoft Excel for beginners full course",
        "youtube": "https://www.youtube.com/results?search_query=excel+beginners+full+course",
        "ms_learn": "",
    },
    {
        "name": "Excel Fundamentals",
        "teaches": ["Excel"],
        "prerequisites": ["Excel"],
        "time": 15, "difficulty": 1, "cost": 0,
        "provider": "Microsoft Learn", "resource_type": "course",
        "topics": ["Descriptive statistics", "Probability", "Sampling", "Statistical inference"],
        "ms_learn": "https://learn.microsoft.com/en-us/training/paths/excel-fundamentals/",
        "youtube": "https://www.youtube.com/results?search_query=excel+fundamentals+course",
    },

]
