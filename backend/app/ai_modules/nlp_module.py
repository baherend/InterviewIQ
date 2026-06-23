import random

_TRANSCRIPTS = [
    "I have over four years of experience in software engineering, primarily focused on backend systems and API design. In my most recent role I led the migration of a monolithic service to microservices, which reduced deployment times by 60 percent.",
    "My greatest strength is my adaptability. When our team had to pivot to a completely new tech stack mid-project, I proactively learned the new tools and helped onboard the rest of the team, which kept us on schedule.",
    "I resolved a major conflict between two senior engineers by facilitating a structured discussion focused on the technical merits of each approach rather than personal preferences. We agreed on a hybrid solution that both parties were satisfied with.",
    "I believe leadership means empowering others to do their best work. I focus on removing blockers, setting clear goals, and providing honest, timely feedback so every team member can grow professionally.",
    "When I encountered a critical bug two hours before a production release, I stayed calm, quickly isolated the root cause using binary search through recent commits, applied a targeted fix, and wrote a regression test before deploying.",
]


def run_nlp(audio_path: str) -> dict:
    """
    NLP AI module — transcribes audio and evaluates content quality and filler usage.
    Production replacement: OpenAI Whisper for STT + LLM-based answer scoring.
    """
    base = random.uniform(58, 94)
    nlp_score = round(max(0.0, min(100.0, base + random.gauss(0, 4))), 2)

    filler_count = random.randint(0, 11)
    transcript = random.choice(_TRANSCRIPTS)
    relevance_score = round(random.uniform(0.60, 1.00), 2)
    coherence_score = round(random.uniform(0.55, 1.00), 2)
    keyword_hits = random.randint(3, 14)

    return {
        "nlp_score": nlp_score,
        "filler_count": filler_count,
        "transcript": transcript,
        "relevance_score": relevance_score,
        "coherence_score": coherence_score,
        "keyword_hits": keyword_hits,
    }
