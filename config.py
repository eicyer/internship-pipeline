SKILLS = [
    "Python", "React", "Node.js", "Java", "Flask", "scikit-learn",
    "PySpark", "MLlib", "Pandas", "Claude API", "Claude Code", "Anthropic API",
    "PostgreSQL", "Git", "Supabase", "Railway", "Vercel",
]

# Company `id`s Sonnet is allowed to rewrite bullets for (pipeline/latex_tailor.py).
# Empty until you hand over the list of companies worth tailoring for.
LATEX_TAILOR_COMPANIES: list[str] = []

EXPERIENCES = [
    {
        "id": "turkish_technology",
        "section": "experience",
        "company": "Turkish Technology (Turkish Airlines Subsidiary)",
        "role": "Software Engineer Intern",
        "location": "Istanbul, Turkey",
        "time": "June 2026 -- July 2026",
        "skills": ["JWT auth", "API security", "React", "data pipelines", "test coverage", "iframe embedding", "postMessage"],
        "bullets": [
            "Engineered a secure multi-partner data-sharing API (Cargy/TK GO), eliminating an unauthenticated data-leak by architecting scoped JWT auth with fail-closed key verification and automated test coverage",
            "Built an idempotent COMIS/JMS ingestion pipeline replacing a manual shipment data-entry workflow, with a fault-tolerant parsing layer backed by 191 lines of edge-case test coverage",
            "Implemented an embeddable live-tracking iframe for external partners, unifying three user views (partner, demo, operator) via a token-scoped React component with postMessage resizing and error handling",
        ],
    },
    {
        "id": "cornell_dti",
        "section": "experience",
        "company": "Cornell Digital Tech and Innovation",
        "role": "Software Developer",
        "location": "Ithaca, NY",
        "time": "November 2025 -- Present",
        "skills": ["React", "DynamoDB", "PostgreSQL", "database migration", "JWT", "auth", "full-stack"],
        "bullets": [
            "Shipped the end-to-end ride-request workflow, model, and UI, enabling 100+ test riders to onboard smoothly",
            "Leading a DynamoDB-to-PostgreSQL migration to unlock horizontal scalability across 3 servers",
            "Identified and resolved a JWT security vulnerability affecting authentication across 3 API endpoints",
        ],
    },
    {
        "id": "tubitak",
        "section": "experience",
        "company": "TUBITAK - The Scientific and Technological Research Council of Turkey",
        "role": "Machine Learning Intern",
        "location": "Gebze, Turkey",
        "time": "June 2023 -- July 2023",
        "skills": ["PySpark", "ML models", "autoencoder", "distributed systems", "data pipelines", "Python"],
        "bullets": [
            "Engineered 2 PySpark pipelines processing 4 GB of data for monthly CPI and regional indices reporting",
            "Improved ML model accuracy from 0.65 to 0.87 by deploying an autoencoder",
        ],
    },
    {
        "id": "pioneer_academics",
        "section": "experience",
        "company": "Pioneer Academics Research Institute, Oberlin College",
        "role": "Data Science Researcher",
        "location": "Remote",
        "time": "June 2024 -- September 2024",
        "skills": ["NLP", "LDA", "VADER", "data analysis", "pandas"],
        "bullets": [
            "Analyzed 3.6M+ tweets with NLP (LDA, VADER) to classify bot strategies and behavioral patterns",
        ],
    },
    {
        "id": "cornell_dining_planner",
        "section": "project",
        "company": "Cornell Dining Planner",
        "role": "",
        "location": "",
        "time": "July 2026 -- Present",
        "tech_stack": "FastAPI, PostgreSQL, React Native, Expo, OAuth",
        "skills": ["FastAPI", "PostgreSQL", "React Native", "Expo", "OAuth", "optimization", "iOS"],
        "bullets": [
            "Built a personalization engine---OAuth login, macro/calorie goals, allergen/diet constraints, preference tags---feeding an optimizer that solves exact meal portions to each user's macro targets across 10 dining halls",
            "Built a FastAPI + Postgres backend and one Expo/React Native codebase shipping as an iOS app and a desktop website, grounding 255 menu items in real USDA nutrition data (230 matched, 0 failures)",
        ],
    },
    {
        "id": "internship_pipeline_agent",
        "section": "project",
        "company": "Internship Pipeline Agent",
        "role": "",
        "location": "",
        "time": "June 2026 -- Present",
        "tech_stack": "Python, Anthropic API, GitHub, Google Sheets, Telegram",
        "skills": ["Python", "Anthropic API", "GitHub API", "Google Sheets API", "Telegram API", "agentic pipelines"],
        "bullets": [
            "Built an agentic pipeline integrating 5+ APIs (Anthropic, GitHub, Google Sheets, Telegram) to discover and score listings daily",
            "Architected a 3-stage cost-gating funnel (regex, Haiku fit-score, 7/10 gate) capping Sonnet rewrites to $\\sim$20/week",
        ],
    },
    {
        "id": "ara_hackathon",
        "section": "project",
        "company": "ARA X Cornell Hackathon",
        "role": "",
        "location": "",
        "time": "April 2026",
        "tech_stack": "Ara SDK, Claude Code, Gmail API, Slack API",
        "skills": ["AI agents", "Ara SDK", "Gmail API", "Slack API", "Claude Code"],
        "bullets": [
            "Built an AI agent using Ara SDK to scan Gmail and Slack for commitments and surface overdue items",
            "Delivered a working agent from schema to production in one day using Claude Code to scaffold and refine tool logic",
        ],
    },
    {
        "id": "tournaid",
        "section": "project",
        "company": "Istanbul Tournament Management App: Tournaid",
        "role": "",
        "location": "",
        "time": "September 2023 -- May 2025",
        "tech_stack": "Django, Python",
        "skills": ["Django", "Python", "full-stack", "automation"],
        "bullets": [
            "Built a Django full-stack platform to automate attendance and scoring workflows through modular design",
            "Led end-to-end delivery to generate \\$120 in revenue and engage 500+ users through iterative prototyping",
        ],
    },
    {
        "id": "wsdc",
        "section": "experience",
        "company": "World Schools Debating Championship (WSDC)",
        "role": "Turkish National Debate Team Captain",
        "location": "",
        "time": "March 2024 -- August 2025",
        "skills": ["leadership", "public speaking", "sponsorship", "fundraising"],
        "bullets": [
            "Achieved \\#1 speaker ranking in Turkey; pitched to 8+ sponsors and secured \\$5K in funding",
        ],
    },
]
