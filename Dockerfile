# syntax=docker/dockerfile:1.6
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app/src"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv and sync deps into the project venv
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    python -m pip install --upgrade pip uv \
    && uv sync --frozen --no-dev --no-install-project

# Copy app code
COPY . .

EXPOSE 8000

CMD ["uv", "run", "fastapi", "run", "src/ark_root_resolver/main.py", "--proxy-headers", "--host", "0.0.0.0", "--port", "8000"]