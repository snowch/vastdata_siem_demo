FROM python:3.12-slim-bookworm

WORKDIR /app

# Install git for pip to clone repositories
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
