FROM python:3.11-slim

# Install system dependencies for Scapy and network tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    tcpdump \
    net-tools \
    iputils-ping \
    iproute2 \
    netcat-openbsd \
    iptables \
    bridge-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip install --no-cache-dir \
    scapy \
    flask \
    flask-cors \
    requests \
    kafka-python

# Create directories
RUN mkdir -p /src/simulator

# Copy traffic generation scripts
COPY src/ /src/simulator/

# Set working directory
WORKDIR /src/simulator

# Expose port for web interface
EXPOSE 8080

# Default command
CMD ["python3", "simulator_server.py"]
