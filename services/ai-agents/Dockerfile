# Use a Python base image
FROM python:3.10-slim-bookworm

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install uv && uv pip install --system -r requirements.txt

# Pre-download the SentenceTransformer model
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Copy the source code
COPY src/ ./src/
COPY templates/ ./templates/

# Expose the port Flask runs on
EXPOSE 5000

# Command to run the Flask application
CMD ["python", "src/web_ui.py"]
