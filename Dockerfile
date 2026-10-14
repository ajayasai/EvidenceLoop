# Portable guided demonstration: build once, run one ephemeral CPU container.
FROM node:24-bookworm-slim AS frontend
WORKDIR /build/apps/web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY apps/web/ ./
COPY contracts/ /build/contracts/
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    EVIDENCELOOP_PUBLIC_DEMO=true PORT=7860
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-15 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 app
WORKDIR /app
COPY requirements.lock.txt ./
RUN python -m pip install --no-cache-dir -r requirements.lock.txt
COPY --chown=app:app services/ ./services/
COPY --chown=app:app contracts/ ./contracts/
COPY --chown=app:app evidence/synthetic_nonclinical.json ./evidence/synthetic_nonclinical.json
COPY --chown=app:app scripts/migrate_db.py scripts/deploy_entrypoint.py ./scripts/
COPY --from=frontend --chown=app:app /build/apps/web/dist/ ./apps/web/dist/
USER 1000:1000
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','7860')+'/api/health',timeout=4)"
CMD ["python", "scripts/deploy_entrypoint.py"]
