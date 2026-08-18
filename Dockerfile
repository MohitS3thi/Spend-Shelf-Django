FROM python:3.12-slim as builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libcairo2-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./

RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=expense_tracker.settings \
    DJANGO_DEBUG=False \
    DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r django && useradd -r -g django django

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY --chown=django:django . .

RUN mkdir -p /app/data && \
    python manage.py collectstatic --noinput && \
    chown -R django:django /app

USER django

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/').read(); exit(0)" || exit 1

CMD ["gunicorn", "expense_tracker.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]
