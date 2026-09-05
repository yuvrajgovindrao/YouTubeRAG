from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    # Application & Environment
    ENVIRONMENT: str = Field(default="development", description="development | production")
    
    # Video Ingestion Cap
    MAX_VIDEOS_PER_COLLECTION: int = Field(default=999, description="Max videos per collection (5 in hosted)")
    
    # Session Management
    SESSION_TTL_SECONDS: int = Field(default=0, description="Session TTL in seconds (0 = disabled in local, 7200 in hosted)")
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = Field(default=False, description="Enable rate limiting on endpoints")
    RATE_LIMIT_PER_HOUR: int = Field(default=10, description="Allowed requests per hour if rate limiting enabled")
    
    # Gemini AI
    GEMINI_API_KEY: str = Field(default="", description="Google Gemini API Key")
    GEMINI_EMBEDDING_MODEL: str = Field(default="gemini-embedding-001", description="Gemini embedding model name")
    EMBEDDING_DIMENSION: int = Field(default=768, description="Vector embedding dimension")
    GEMINI_CHAT_MODEL: str = Field(default="gemini-1.5-flash", description="Gemini text generation model")
    
    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/youtube_rag",
        description="Async PostgreSQL connection string"
    )
    SYNC_DATABASE_URL: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/youtube_rag",
        description="Sync PostgreSQL connection string (for migrations/sync ops if needed)"
    )
    
    # Retrieval
    SIMILARITY_THRESHOLD: float = Field(default=0.55, description="Cosine similarity threshold for chunk retrieval")
    MAX_SOURCES_RETURNED: int = Field(default=4, description="Max distinct video sources returned")

    # CORS
    CORS_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173",
        description="Comma-separated allowed origins"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
