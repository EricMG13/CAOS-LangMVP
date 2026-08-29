FROM node:26-slim@sha256:c0753125a3789977aefe869cbebccf70e3cfd7ea84ca48547458f02e4f1d7146 AS frontend
WORKDIR /frontend
COPY caos/frontend/package.json caos/frontend/package-lock.json ./
RUN npm ci
COPY caos/frontend/ ./
RUN npm run build

FROM python:3.14-slim@sha256:ce40764625a4ff50df3548277632e7f96c4e77fe75fa848aae9885476e7df5a4 AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HOST=0.0.0.0 PORT=8000 ENVIRONMENT=production
WORKDIR /app
RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*
COPY caos/server/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && rm -rf /usr/local/lib/python3.14/site-packages/pip \
        /usr/local/lib/python3.14/site-packages/pip-*.dist-info \
        /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.14
COPY caos/server/ ./
COPY caos/deploy/verify_image_resources.py ./verify_image_resources.py
COPY --from=frontend /frontend/out ./static
RUN useradd -m -u 10001 caos && mkdir -p /vault && chown -R caos:caos /app /vault
RUN python -m compileall -q .
RUN python verify_image_resources.py

FROM runtime AS worker
COPY caos/tests/fixtures/cp_model/ /image-fixtures/cp_model/
RUN apt-get update \
    && apt-get install -y --no-install-recommends libreoffice-calc \
    && rm -rf /var/lib/apt/lists/*
USER caos
RUN python verify_image_resources.py --runtime worker
CMD ["python", "worker.py"]

FROM runtime AS app
USER caos
RUN python verify_image_resources.py --runtime app
EXPOSE 8000
CMD ["python", "run.py"]
