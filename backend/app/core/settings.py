from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "Plan Review AI"
    environment: str = "dev"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/planreview"

settings = Settings()
