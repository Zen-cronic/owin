# Owin: answer screen + JSON API on one port. Python 3.12 slim, non-root, Poetry-installed, no secrets baked in.
# Build:  docker build --platform linux/amd64 -t owin:$(git rev-parse --short HEAD) .
# Run:    docker run --rm -p 8080:8080 owin:<tag>          (demo mode: no keys needed)
# Config comes only from env vars: TOKEN_FACTORY_API_KEY, TAVILY_API_KEY, OWIN_STATE_DIR, PORT (see DEPLOY.md).

# Build stage: Poetry installs the project (editable, so ROOT=/app finds data/) into /venv.
FROM python:3.12-slim AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 POETRY_NO_INTERACTION=1 POETRY_VIRTUALENVS_CREATE=false
RUN pip install "poetry==2.5.1"
WORKDIR /app
COPY pyproject.toml poetry.lock README.md ./
COPY owin ./owin
RUN python -m venv /venv \
 && VIRTUAL_ENV=/venv PATH="/venv/bin:$PATH" poetry install --only main --no-ansi \
 && /venv/bin/owin --help > /dev/null

# Runtime stage: no Poetry, no build tools, no fixtures/raw, no .env.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PATH="/venv/bin:$PATH" VIRTUAL_ENV=/venv \
    OWIN_HOST=0.0.0.0 PORT=8080 \
    OWIN_LEDGER=/app/var/ledger/usage.jsonl
RUN useradd --system --uid 10001 --user-group --create-home --home-dir /home/owin owin
WORKDIR /app
COPY --from=build /venv /venv
# The build context is an allowlist (.dockerignore): code, committed data, recorded runs, demo fixtures.
COPY . /app
# Writable only where a refresh job writes scratch files; served data stays root-owned and read-only.
RUN mkdir -p /app/var/state /app/var/ledger /app/fixtures/raw \
 && chown -R owin:owin /app/var /app/fixtures/raw \
 && chown owin:owin /app/fixtures/manifest.json \
 && test ! -e /app/.env
USER owin
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=4s --start-period=5s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('PORT','8080'), timeout=3)"
# Shell form so $PORT from the platform is honoured; exec keeps owin as PID 1 for clean SIGTERM.
CMD ["sh", "-c", "exec owin serve --host \"${OWIN_HOST:-0.0.0.0}\" --port \"${PORT:-8080}\""]
