FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/app

RUN apt-get update \
    && apt-get install --no-install-recommends -y libgomp1 postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-lock.txt /app/requirements-lock.txt
RUN pip install --no-cache-dir -r /app/requirements-lock.txt

COPY app /app/app
COPY sample-data /app/sample-data
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /tmp/prometheus_multiproc /data/task_uploads/knowledge /data/task_uploads/attachments \
    && chown -R appuser:appuser /app
RUN chown -R appuser:appuser /tmp/prometheus_multiproc /data/task_uploads
USER appuser
WORKDIR /app

EXPOSE 8000

CMD ["python", "/app/app/scripts/run_backend.py"]
