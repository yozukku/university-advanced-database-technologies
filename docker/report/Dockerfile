FROM python:3.13-slim-trixie@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        pandoc libreoffice-writer-nogui libreoffice-impress-nogui python3-uno \
        fonts-crosextra-carlito fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv==0.13.8

ENV UV_PROJECT_ENVIRONMENT=/opt/ztb-python
ENV UV_PYTHON_DOWNLOADS=never
ENV PATH="/opt/ztb-python/bin:$PATH"
WORKDIR /opt/ztb-dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --only-group report

WORKDIR /workspace
