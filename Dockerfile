FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Separate layer: dependencies are not reinstalled on every code change.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Do not run the app as root.
RUN useradd --create-home --uid 1000 app && chown -R app /app
USER app

EXPOSE 8000

# Migrations first, then the server. PORT is set by most hosting platforms.
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
