FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANG=es_ES.UTF-8 \
    LC_ALL=es_ES.UTF-8 \
    CEREZAS_CONFIG_DIR=/app/config \
    CEREZAS_ASSETS_DIR=/app/assets \
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
COPY assets/fic-report-assets.zip.b64 /tmp/fic-report-assets.zip.b64

RUN mkdir -p /app/assets \
    && echo "4833d777457119f0506431d61d9c0457f752e253d059d4de168f921225d7321b  /tmp/fic-report-assets.zip" > /tmp/fic-report-assets.sha256 \
    && base64 -d /tmp/fic-report-assets.zip.b64 > /tmp/fic-report-assets.zip \
    && sha256sum -c /tmp/fic-report-assets.sha256 \
    && python -m zipfile -e /tmp/fic-report-assets.zip /app/assets \
    && cp /app/assets/logos/logo_fic.png /app/assets/logo_fic.png \
    && rm -rf /app/assets/__MACOSX /tmp/fic-report-assets.zip /tmp/fic-report-assets.zip.b64 /tmp/fic-report-assets.sha256

RUN pip install --no-cache-dir .

VOLUME ["/data"]

HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
  CMD ["cerezas-pipeline", "health"]

ENTRYPOINT ["cerezas-pipeline"]
CMD ["schedule"]
