# Azami backend image. Build context = repo root:
#   docker build -f backend/Dockerfile -t azami/api .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first for layer caching.
COPY backend/pyproject.toml /app/backend/pyproject.toml
RUN pip install --no-cache-dir "/app/backend[prod]" 2>/dev/null || \
    pip install --no-cache-dir fastapi "uvicorn[standard]" pydantic pydantic-settings \
        SQLAlchemy PyJWT bcrypt cryptography httpx dnspython PyYAML tldextract \
        phonenumbers python-multipart websockets "psycopg[binary]" redis

# App code + data-source catalogs.
COPY backend/ /app/backend/
COPY data_sources/ /app/data_sources/

WORKDIR /app/backend
RUN pip install --no-cache-dir --no-deps .

EXPOSE 8099
# A non-root user for the API itself (tool execution is isolated in runner containers).
RUN useradd -m -u 1000 azami && chown -R azami /app
USER azami

CMD ["uvicorn", "azami.main:app", "--host", "0.0.0.0", "--port", "8099"]
