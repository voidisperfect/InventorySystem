FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app


ENV PYTHONPATH=/app/src

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-cache

COPY . .

CMD ["uv", "run", "uvicorn", "order_app.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "src"]