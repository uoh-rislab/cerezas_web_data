FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANG=es_ES.UTF-8 \
    LC_ALL=es_ES.UTF-8 \
    CEREZAS_CONFIG_DIR=/app/config \
    CEREZAS_ASSETS_DIR=/app/config/assets \
    CEREZAS_DATA_ROOT=/data

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
       fonts-dejavu-core locales libnss3 libatk-bridge2.0-0 libgtk-3-0 libgbm1 libasound2 \
    && sed -i 's/^# *\(es_ES.UTF-8 UTF-8\)/\1/' /etc/locale.gen \
    && locale-gen \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY config ./config

RUN pip install --no-cache-dir .

VOLUME ["/data"]

HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
  CMD ["cerezas-pipeline", "health"]

ENTRYPOINT ["cerezas-pipeline"]
CMD ["schedule"]
