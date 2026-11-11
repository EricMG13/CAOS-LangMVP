FROM node:26-slim@sha256:c0753125a3789977aefe869cbebccf70e3cfd7ea84ca48547458f02e4f1d7146 AS frontend
WORKDIR /frontend
COPY caos/frontend/package.json caos/frontend/package-lock.json ./
RUN npm ci
COPY caos/frontend/ ./
RUN npm run build

FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928 AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HOST=0.0.0.0 PORT=8000 ENVIRONMENT=production
WORKDIR /app
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends fonts-noto-cjk pango1.0-tools \
    && rm -rf /var/lib/apt/lists/*
COPY caos/server/requirements.txt ./requirements.txt
# --require-hashes: requirements.txt is a fully-pinned, hashed lock compiled from
# pyproject.toml. pip refuses the install if any requirement lacks a hash or if a
# downloaded artifact does not match, so a compromised re-release of an
# already-pinned version cannot enter the image.
RUN pip install --no-cache-dir --require-hashes -r requirements.txt \
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
