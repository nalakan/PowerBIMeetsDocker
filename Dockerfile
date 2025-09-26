FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl git build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install only what's needed
#RUN pip install --no-cache-dir ms-fabric-cli requests
RUN pip install --no-cache-dir --upgrade ms-fabric-cli requests

# Copy files
COPY deploy.py /app/deploy.py
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
