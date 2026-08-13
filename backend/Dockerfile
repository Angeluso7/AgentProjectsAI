FROM python:3.11-slim
WORKDIR /app
COPY app /app/app
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir fastapi uvicorn[standard] sqlalchemy alembic pydantic pydantic-settings psycopg[binary]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
