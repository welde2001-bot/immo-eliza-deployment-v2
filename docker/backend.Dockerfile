FROM python:3.11-slim

# XGBoost needs OpenMP runtime on slim Debian images
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps first for better Docker caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your API code + runtime artifacts
COPY api ./api
COPY artifacts ./artifacts
COPY data ./data

ENV PYTHONUNBUFFERED=1

# Render provides PORT; default to 10000 when PORT is not set
CMD ["sh", "-c", "uvicorn api.app:app --host 0.0.0.0 --port ${PORT:-10000}"]
