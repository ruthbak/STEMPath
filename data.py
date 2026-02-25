skills = [
    "Python", "SQL", "Statistics", "Machine Learning",
    "Data Visualization", "Networking", "Linux",
    "Security Basics", "Cloud", "Git", "APIs", "TensorFlow"
]

courses = [
    {
        "name": "Python for Everybody",
        "teaches": ["Python"],
        "prerequisites": [],
        "time": 30,
        "difficulty": 1,
        "cost": 0,
        "provider": "Coursera",
        "ms_learn": "https://learn.microsoft.com/en-us/training/paths/beginner-python/",
        "youtube": "https://www.youtube.com/results?search_query=python+for+beginners+full+course"
    },
    {
        "name": "SQL Fundamentals",
        "teaches": ["SQL"],
        "prerequisites": [],
        "time": 20,
        "difficulty": 1,
        "cost": 0,
        "provider": "edX",
        "ms_learn": "https://learn.microsoft.com/en-us/training/paths/get-started-querying-with-transact-sql/",
        "youtube": "https://www.youtube.com/results?search_query=sql+fundamentals+full+course"
    },
    {
        "name": "Intro to Statistics",
        "teaches": ["Statistics"],
        "prerequisites": ["Python"],
        "time": 40,
        "difficulty": 2,
        "cost": 0,
        "provider": "edX",
        "ms_learn": "https://learn.microsoft.com/en-us/training/paths/data-science-know-your-data/",
        "youtube": "https://www.youtube.com/results?search_query=statistics+for+data+science+full+course"
    },
    {
        "name": "Data Analysis with Python",
        "teaches": ["Data Visualization"],
        "prerequisites": ["Python", "SQL"],
        "time": 40,
        "difficulty": 2,
        "cost": 0,
        "provider": "Coursera",
        "ms_learn": "https://learn.microsoft.com/en-us/training/paths/visualize-data-power-bi/",
        "youtube": "https://www.youtube.com/results?search_query=data+analysis+python+pandas+matplotlib+full+course"
    },
    {
        "name": "ML Basics",
        "teaches": ["Machine Learning"],
        "prerequisites": ["Python", "Statistics"],
        "time": 60,
        "difficulty": 3,
        "cost": 49,
        "provider": "edX",
        "ms_learn": "https://learn.microsoft.com/en-us/training/paths/introduction-machine-learning/",
        "youtube": "https://www.youtube.com/results?search_query=machine+learning+full+course+beginners"
    },
    {
        "name": "TensorFlow Fundamentals",
        "teaches": ["TensorFlow"],
        "prerequisites": ["Machine Learning"],
        "time": 50,
        "difficulty": 3,
        "cost": 0,
        "provider": "Google",
        "ms_learn": "https://learn.microsoft.com/en-us/training/paths/introduction-machine-learning/",
        "youtube": "https://www.youtube.com/results?search_query=tensorflow+full+course+beginners"
    },
    {
        "name": "Networking Fundamentals",
        "teaches": ["Networking"],
        "prerequisites": [],
        "time": 35,
        "difficulty": 2,
        "cost": 0,
        "provider": "Cisco NetAcad",
        "ms_learn": "https://learn.microsoft.com/en-us/training/paths/implement-windows-server-networking/",
        "youtube": "https://www.youtube.com/results?search_query=networking+fundamentals+full+course"
    },
    {
        "name": "Linux Command Line Basics",
        "teaches": ["Linux"],
        "prerequisites": [],
        "time": 15,
        "difficulty": 1,
        "cost": 0,
        "provider": "edX",
        "ms_learn": "https://learn.microsoft.com/en-us/training/paths/azure-linux/",
        "youtube": "https://www.youtube.com/results?search_query=linux+command+line+full+course+beginners"
    },
    {
        "name": "CompTIA Security+ Prep",
        "teaches": ["Security Basics"],
        "prerequisites": ["Networking"],
        "time": 60,
        "difficulty": 3,
        "cost": 30,
        "provider": "CompTIA",
        "ms_learn": "https://learn.microsoft.com/en-us/training/paths/security-compliance-identity-fundamentals/",
        "youtube": "https://www.youtube.com/results?search_query=comptia+security+plus+full+course"
    },
    {
        "name": "AWS Cloud Practitioner",
        "teaches": ["Cloud"],
        "prerequisites": ["Networking"],
        "time": 30,
        "difficulty": 2,
        "cost": 0,
        "provider": "AWS / Microsoft Learn",
        "ms_learn": "https://learn.microsoft.com/en-us/training/paths/az-900-describe-cloud-concepts/",
        "youtube": "https://www.youtube.com/results?search_query=aws+cloud+practitioner+full+course"
    },
    {
        "name": "Git & GitHub for Beginners",
        "teaches": ["Git"],
        "prerequisites": [],
        "time": 10,
        "difficulty": 1,
        "cost": 0,
        "provider": "GitHub",
        "ms_learn": "https://learn.microsoft.com/en-us/training/paths/intro-to-vc-git/",
        "youtube": "https://www.youtube.com/results?search_query=git+github+full+course+beginners"
    },
    {
        "name": "REST API Development",
        "teaches": ["APIs"],
        "prerequisites": ["Python"],
        "time": 25,
        "difficulty": 2,
        "cost": 0,
        "provider": "edX",
        "ms_learn": "https://learn.microsoft.com/en-us/training/paths/build-serverless-full-stack-apps-azure/",
        "youtube": "https://www.youtube.com/results?search_query=rest+api+development+python+full+course"
    },
    {
        "name": "HTML & CSS Fundamentals",
        "teaches": ["CSS", "HTML"],
        "prerequisites": [],
        "time": 15,
        "difficulty": 1,
        "cost": 0,
        "provider": "MDN / freeCodeCamp",
        "ms_learn": "https://learn.microsoft.com/en-us/training/paths/web-development-101/",
        "youtube": "https://www.youtube.com/results?search_query=html+css+full+course+beginners"
    },
    {
        "name": "JavaScript Basics",
        "teaches": ["JavaScript"],
        "prerequisites": ["HTML", "CSS"],
        "time": 30,
        "difficulty": 2,
        "cost": 0,
        "provider": "freeCodeCamp",
        "ms_learn": "https://learn.microsoft.com/en-us/training/paths/web-development-101/",
        "youtube": "https://www.youtube.com/results?search_query=javascript+full+course+beginners"
    },
    {
        "name": "Java Programming Fundamentals",
        "teaches": ["Java"],
        "prerequisites": [],
        "time": 40,
        "difficulty": 2,
        "cost": 0,
        "provider": "edX",
        "ms_learn": "https://learn.microsoft.com/en-us/training/paths/java-se-fundamentals/",
        "youtube": "https://www.youtube.com/results?search_query=java+programming+full+course+beginners"
    },
    {
        "name": "Statistics for Data Science",
        "teaches": ["Statistics"],
        "prerequisites": [],
        "time": 35,
        "difficulty": 2,
        "cost": 0,
        "provider": "Coursera",
        "ms_learn": "https://learn.microsoft.com/en-us/training/paths/data-science-know-your-data/",
        "youtube": "https://www.youtube.com/results?search_query=statistics+for+data+science+beginners"
    },
]