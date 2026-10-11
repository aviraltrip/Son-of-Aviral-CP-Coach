FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_PATH=/app/data/cp_coach.db \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    g++ \
    gcc \
    default-jdk-headless \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY evals/ ./evals/
COPY tests/ ./tests/
COPY pyproject.toml .
COPY README.md .
COPY healthcheck.py .

RUN groupadd -r -g 1001 appgroup && \
    useradd -r -u 1001 -g appgroup -d /home/appuser -m -s /bin/bash appuser

ENV HOME=/home/appuser

RUN mkdir -p /app/data /home/appuser/.cache && \
    chown -R appuser:appgroup /app /home/appuser

USER appuser

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python healthcheck.py || exit 1

ENTRYPOINT ["streamlit", "run", "app/ui/streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
