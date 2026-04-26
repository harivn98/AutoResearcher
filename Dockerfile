# Dockerfile — FastAPI app for AutoResearcher

# 1. Base image
FROM python:3.10-slim

# 2. Working directory
WORKDIR /app

# 3. Install system deps (if you later need them; keep minimal for now)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 4. Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# 5. Copy application code
COPY app ./app

# (Optional) copy scripts if you want eval inside container too
# COPY scripts ./scripts

# 6. Expose port
EXPOSE 8000

# 7. Default envs (can be overridden by docker compose)
ENV OLLAMA_BASE_URL=http://host.docker.internal:11434 \
    OLLAMA_MODEL=llama3.2 \
    CHROMA_PERSIST_DIR=/app/chroma_db

# 8. Run FastAPI with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]