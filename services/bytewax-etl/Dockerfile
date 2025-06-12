FROM python:3.12-slim-bookworm

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bytewax_ocsf_vastdb.py .
COPY ocsf_mappings.py .

CMD ["python", "-m", "bytewax.run", "bytewax_ocsf_vastdb"]
