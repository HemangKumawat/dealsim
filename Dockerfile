# ── Stage 1: CSS build ────────────────────────────────────────────────────────
# Uses Node only to compile Tailwind. The output file is copied into the final
# Python image; Node itself is not present at runtime.
FROM node:20-slim AS css-builder

WORKDIR /build

COPY package.json ./
RUN npm install --prefer-offline

COPY tailwind.config.js ./
COPY src/styles/input.css src/styles/input.css
# Static HTML/JS files are needed so Tailwind can tree-shake unused classes.
COPY static/ static/
COPY src/ src/

RUN npm run build:css


# ── Stage 2: Python runtime ───────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency resolution
RUN pip install --no-cache-dir uv

# Copy everything needed for install
COPY pyproject.toml .
COPY src/ src/
COPY static/ static/

# Drop the compiled CSS into the static directory
COPY --from=css-builder /build/static/tailwind.out.css static/tailwind.out.css

# Install the package and its dependencies
RUN uv pip install --system .

# Create non-root user and data directory
# /app/data is the canonical data path used by docker-compose.yml and .env.example.
RUN useradd --create-home --shell /bin/bash dealsim \
    && mkdir -p /app/data \
    && chown dealsim:dealsim /app/data

USER dealsim

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Worker count is controlled by DEALSIM_WORKERS env var (set in .env / compose).
# Default to 1 here so the image is runnable standalone; compose overrides this.
CMD ["sh", "-c", "uvicorn dealsim_mvp.app:app --host 0.0.0.0 --port 8000 --workers ${DEALSIM_WORKERS:-1}"]
