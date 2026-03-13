"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration.

    All values are loaded from environment variables or a .env file.
    """

    # Azure SQL
    AZURE_SQL_CONNECTION_STRING: str = ""

    # Azure Blob Storage
    # Function App has these set as AZURE_BLOB_CONNECTION_STRING / BLOB_CONTAINER_NAME
    AZURE_BLOB_CONNECTION_STRING: str = ""
    BLOB_CONTAINER_NAME: str = "images"
    BLOB_THUMBS_CONTAINER_NAME: str = "thumbnails"
    BLOB_RENDERS_CONTAINER_NAME: str = "renders"

    # Azure AI Search
    AZURE_SEARCH_ENDPOINT: str = ""
    AZURE_SEARCH_KEY: str = ""
    AZURE_SEARCH_INDEX: str = "stearman-index"

    # WorkOS AuthKit
    WORKOS_API_KEY: str = ""
    WORKOS_CLIENT_ID: str = ""

    # Deploy webhook (for CI to update WEBSITE_RUN_FROM_PACKAGE via ARM)
    DEPLOY_KEY: str = ""
    AZURE_SUBSCRIPTION_ID: str = ""
    AZURE_RESOURCE_GROUP: str = ""
    AZURE_FUNCTION_APP_NAME: str = ""

    # CORS — defaults to * for production; override for stricter local dev
    CORS_ORIGINS: str = "*"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        val = self.CORS_ORIGINS.strip()
        if val == "*":
            return ["*"]
        return [origin.strip() for origin in val.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
