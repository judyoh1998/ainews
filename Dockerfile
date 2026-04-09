FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.34.0" \
    "pydantic>=2.0" \
    "pydantic-settings>=2.0" \
    "anthropic>=0.40.0" \
    "beautifulsoup4>=4.12.0" \
    "python-multipart>=0.0.9"

# Copy application code
COPY app/ app/
COPY static/ static/
COPY run.py seed.py ./

# Create data directory (will be overridden by Railway volume mount)
RUN mkdir -p /data

# Default env vars for Railway
ENV NEKO_DATABASE_PATH=/data/neko.db \
    NEKO_HOST=0.0.0.0 \
    NEKO_DEBUG=false

EXPOSE 8000

# Seed demo data on startup, then run the server
CMD python seed.py && python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
