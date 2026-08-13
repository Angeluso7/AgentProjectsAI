FROM python:3.11-slim
WORKDIR /app
COPY ../pyproject.toml /tmp/pyproject.toml
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir fastapi uvicorn[standard] sqlalchemy alembic pydantic pydantic-settings psycopg[binary]
COPY app /app/app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
