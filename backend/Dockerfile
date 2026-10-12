# FinTrace API image. Build from the repository root (it needs ml/ and data/sample/):
#   docker build -f backend/Dockerfile -t fintrace-api .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first, so code changes do not reinstall them.
COPY ml/pyproject.toml ml/README.md ml/
COPY backend/pyproject.toml backend/
RUN mkdir -p ml/fintrace_ml backend/app \
    && touch ml/fintrace_ml/__init__.py backend/app/__init__.py \
    && pip install -e ./ml -e ./backend

COPY ml/fintrace_ml ml/fintrace_ml
COPY backend/app backend/app
COPY backend/alembic backend/alembic
COPY backend/alembic.ini backend/
COPY data/sample data/sample

# Run as an unprivileged user. ml/artifacts is a volume (models stay out of the image).
RUN useradd --create-home --uid 10001 fintrace \
    && mkdir -p ml/artifacts \
    && chown -R fintrace:fintrace /app/ml/artifacts
USER fintrace

WORKDIR /app/backend
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --retries=6 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')"

# Apply migrations, then serve. Migrations are idempotent, so restarts are safe.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]
