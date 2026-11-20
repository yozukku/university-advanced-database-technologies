FROM python:3.13-slim-bookworm@sha256:a5a7017efc5969e00ae2b91c8eb0631049a569652aa4ffc4501769049ae45c72

RUN pip install --no-cache-dir uv==0.13.8

ENV UV_PROJECT_ENVIRONMENT=/opt/ztb-python
ENV UV_PYTHON_DOWNLOADS=never
ENV PATH="/opt/ztb-python/bin:$PATH"
WORKDIR /opt/ztb-dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev

COPY docker/runner/entrypoint.py /usr/local/bin/bench-runner
WORKDIR /workspace

ENTRYPOINT ["python", "/usr/local/bin/bench-runner"]
