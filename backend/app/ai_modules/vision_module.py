import random


def run_vision(video_path: str) -> dict:
    """
    Vision AI module — analyzes facial expressions, eye contact, and posture.
    Production replacement: MediaPipe + OpenCV face mesh pipeline.
    """
    base = random.uniform(58, 94)
    vision_score = round(max(0.0, min(100.0, base + random.gauss(0, 4))), 2)

    emotions = ["Confident", "Neutral", "Engaged", "Anxious", "Nervous"]
    weights = [0.30, 0.28, 0.22, 0.12, 0.08]
    emotion = random.choices(emotions, weights=weights)[0]

    eye_contact = round(random.uniform(0.42, 0.96), 2)
    posture_score = round(random.uniform(0.50, 1.00), 2)

    return {
        "vision_score": vision_score,
        "emotion": emotion,
        "eye_contact": eye_contact,
        "posture_score": posture_score,
    }
