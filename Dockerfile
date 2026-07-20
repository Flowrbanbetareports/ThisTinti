FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    THISTINTI_AUTO_CREATE_SCHEMA=false

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends openssl poppler-utils postgresql-client tesseract-ocr tesseract-ocr-eng tesseract-ocr-ita \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system thistinti && useradd --system --gid thistinti --home-dir /app thistinti

COPY requirements-linux.lock.txt ./requirements-linux.lock.txt
RUN python -m pip install --no-cache-dir -r requirements-linux.lock.txt

COPY --chown=thistinti:thistinti . .
RUN mkdir -p /app/data/uploads /app/data/quarantine /app/data/rejected \
    && chown -R thistinti:thistinti /app/data

ENTRYPOINT ["python", "scripts/container_entrypoint.py"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/readiness', timeout=3)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
