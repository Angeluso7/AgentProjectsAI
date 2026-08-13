from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "Plan Review AI Hybrid"
    environment: str = "dev"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/planreview"
    redis_url: str = "redis://localhost:6379/0"
    vector_store_path: str = "./memory/vector_index"

settings = Settings()
