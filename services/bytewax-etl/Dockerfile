FROM python:3.12-slim-bookworm

WORKDIR /app

# Install git for pip to clone repositories
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install uv && uv pip install --system -r requirements.txt

# Pre-download the SentenceTransformer model
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
