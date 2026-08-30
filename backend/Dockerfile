FROM python:3.11-slim

WORKDIR /app/backend

RUN apt-get update \
    && apt-get install --no-install-recommends -y ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /app/backend/
COPY InterviewIQ_AI/ /app/InterviewIQ_AI/

RUN mkdir -p \
    /app/storage/uploads \
    /app/backend/storage/answer_segments \
    /app/backend/storage/fusion_uploads \
    /app/InterviewIQ_AI/fusion/outputs/website

EXPOSE 8000

ENV BACKEND_HOST=0.0.0.0
ENV BACKEND_PORT=8000
ENV PYTHONPATH=/app/backend:/app/InterviewIQ_AI

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host ${BACKEND_HOST} --port ${BACKEND_PORT}"]
