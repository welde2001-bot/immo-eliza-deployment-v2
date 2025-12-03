FROM python:3.14-slim

# XGBoost needs OpenMP runtime on slim Debian images
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps first for better Docker caching
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy your backend package + runtime artifacts/data
COPY backend/app /app/app
COPY backend/artifacts /app/artifacts
COPY backend/data /app/data

ENV PYTHONUNBUFFERED=1

# Render provides PORT; default to 10000 when PORT is not set
CMD ["sh", "-c", "uvicorn app.app:app --host 0.0.0.0 --port ${PORT:-10000}"]
