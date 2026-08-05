from sqlalchemy.orm import Session
from app.models.question import Question

SEED_QUESTIONS = [
    # Required local Fusion test question, sourced from the existing
    # reference_docs_250_FINAL_v1.json entry SE-028.
    {
        "question": "\u0645\u0627 \u0647\u0648 TDD \u0648\u0645\u0627 \u062f\u0648\u0631\u062a\u0647\u061f",
        "interview_type": "Technical",
        "track": "Software Engineering",
        "difficulty": "Medium",
        "nlp_reference_id": "SE-028",
    },
    # HR
    {"question": "Tell me about yourself.", "interview_type": "HR", "track": None, "difficulty": "Easy"},
    {"question": "Why should we hire you?", "interview_type": "HR", "track": None, "difficulty": "Medium"},
    {"question": "What are your greatest strengths and weaknesses?", "interview_type": "HR", "track": None, "difficulty": "Medium"},
    {"question": "Why do you want to work here?", "interview_type": "HR", "track": None, "difficulty": "Medium"},
    {"question": "Where do you see yourself in 5 years?", "interview_type": "HR", "track": None, "difficulty": "Medium"},

    # Leadership
    {"question": "Describe a time you led a team through a difficult project.", "interview_type": "Leadership", "track": None, "difficulty": "Hard"},
    {"question": "How do you resolve conflicts within your team?", "interview_type": "Leadership", "track": None, "difficulty": "Medium"},
    {"question": "How do you motivate team members who are underperforming?", "interview_type": "Leadership", "track": None, "difficulty": "Hard"},
    {"question": "Describe the most difficult decision you have made as a leader.", "interview_type": "Leadership", "track": None, "difficulty": "Hard"},
    {"question": "How would you describe your leadership style?", "interview_type": "Leadership", "track": None, "difficulty": "Easy"},

    # Technical - Data Analysis
    {"question": "Explain the difference between INNER JOIN and LEFT JOIN in SQL.", "interview_type": "Technical", "track": "Data Analysis", "difficulty": "Medium"},
    {"question": "What is database normalization and why is it important?", "interview_type": "Technical", "track": "Data Analysis", "difficulty": "Medium"},
    {"question": "Explain the GROUP BY clause and when you would use HAVING vs WHERE.", "interview_type": "Technical", "track": "Data Analysis", "difficulty": "Medium"},
    {"question": "How do you handle missing values in a dataset?", "interview_type": "Technical", "track": "Data Analysis", "difficulty": "Medium"},
    {"question": "What is the difference between descriptive and inferential statistics?", "interview_type": "Technical", "track": "Data Analysis", "difficulty": "Easy"},

    # Technical - Data Science
    {"question": "What is overfitting and how do you prevent it?", "interview_type": "Technical", "track": "Data Science", "difficulty": "Medium"},
    {"question": "Explain the difference between supervised and unsupervised learning.", "interview_type": "Technical", "track": "Data Science", "difficulty": "Easy"},
    {"question": "What is cross-validation and why is it used?", "interview_type": "Technical", "track": "Data Science", "difficulty": "Medium"},
    {"question": "Explain the bias-variance tradeoff in machine learning.", "interview_type": "Technical", "track": "Data Science", "difficulty": "Hard"},
    {"question": "What is the difference between classification and regression problems?", "interview_type": "Technical", "track": "Data Science", "difficulty": "Easy"},

    # Technical - Cybersecurity
    {"question": "Explain the CIA Triad in cybersecurity.", "interview_type": "Technical", "track": "Cybersecurity", "difficulty": "Easy"},
    {"question": "What is SQL injection and how can it be prevented?", "interview_type": "Technical", "track": "Cybersecurity", "difficulty": "Medium"},
    {"question": "What is the difference between authentication and authorization?", "interview_type": "Technical", "track": "Cybersecurity", "difficulty": "Easy"},
    {"question": "How does a firewall work and what are its limitations?", "interview_type": "Technical", "track": "Cybersecurity", "difficulty": "Medium"},
    {"question": "What is phishing and what are common attack techniques?", "interview_type": "Technical", "track": "Cybersecurity", "difficulty": "Easy"},

    # Technical - Software Engineering
    {"question": "Explain the four pillars of Object-Oriented Programming.", "interview_type": "Technical", "track": "Software Engineering", "difficulty": "Medium"},
    {"question": "What is the difference between a Stack and a Queue? Give use cases for each.", "interview_type": "Technical", "track": "Software Engineering", "difficulty": "Easy"},
    {"question": "What is a REST API and what are its key principles?", "interview_type": "Technical", "track": "Software Engineering", "difficulty": "Medium"},
    {"question": "What are the differences between SQL and NoSQL databases?", "interview_type": "Technical", "track": "Software Engineering", "difficulty": "Medium"},
    {"question": "Explain Git branching strategies and best practices.", "interview_type": "Technical", "track": "Software Engineering", "difficulty": "Medium"},
]


def seed_questions(db: Session):
    existing_questions = {
        row[0] for row in db.query(Question.question).all()
    }
    missing = [
        q for q in SEED_QUESTIONS if q["question"] not in existing_questions
    ]
    if missing:
        for q in missing:
            db.add(Question(**q))
        db.commit()
        print(f"[Seed] Inserted {len(missing)} missing questions.")
