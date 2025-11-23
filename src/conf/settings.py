import os

from dotenv import load_dotenv
from loguru import logger
from pydantic import Field, SecretStr
from yarl import URL

from src.conf.base_settings import BaseSettings

load_dotenv()  # Load environment variables from .env file

PREFIX = ""


class DummyConfig(BaseSettings):
    """Example of Config."""

    api_key: str = Field(
        default="",
        description="API key for developer account",
    )
    api_key_secret: SecretStr = Field(
        default=SecretStr(""),
        description="API key secret for developer account",
    )

    class Config:
        env_prefix = f"{PREFIX}DUMMY_"


class DatabaseConfig(BaseSettings):
    """Database configuration parameters."""

    sqlitedb_path: str = Field(default="", description="SQLite file path.")
    host: str = Field(default="localhost", description="PostgreSQL host.")
    port: int = Field(default=5432, description="PostgreSQL host.")
    # LOCAL: Alternatively use docker-compose container name
    postgres_database: str = Field(
        default="postgres", description="PostgreSQL database name."
    )
    postgres_user: str = Field(default="postgres", description="PostgreSQL username.")
    postgres_password: SecretStr = Field(
        default=SecretStr("postgres"), description="PostgreSQL password."
    )

    @property
    def url(self) -> URL:
        """Assemble database URL from settings."""
        return URL.build(
            scheme="postgresql+asyncpg",
            host=self.host,
            port=self.port,
            user=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            path=f"/{self.postgres_database}",
        )

    class Config:
        # Pydantic automatically combines the env_prefix (DB_) with the field
        #  name (host) and converts it to uppercase. DB_ + host -> DB_HOST
        env_prefix = f"{PREFIX}DB_"


class Settings(BaseSettings):
    """Application settings."""

    dummy: DummyConfig = DummyConfig()
    database: DatabaseConfig = DatabaseConfig()
    app_name: str = "MyFastAPIApp"
    debug: bool = False
    ignore_db: bool = False
    secret_key: str = "some-secret-key"  # TODO: SecretStr type
    admin_access_key: str = "mealmap-admin"

    AWS_ACCESS_KEY_ID: str | None = os.environ.get("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: str | None = os.environ.get("AWS_SECRET_ACCESS_KEY")
    AWS_BUCKET_NAME: str | None = os.environ.get("AWS_BUCKET_NAME")
    AWS_REGION_NAME: str | None = os.environ.get("AWS_REGION_NAME")

    for critical_env, name in [
        (AWS_ACCESS_KEY_ID, "AWS_ACCESS_KEY_ID"),
        (AWS_SECRET_ACCESS_KEY, "AWS_SECRET_ACCESS_KEY"),
        (AWS_BUCKET_NAME, "AWS_BUCKET_NAME"),
    ]:
        if not critical_env:
            logger.error(f"{name} not found in environment variables")

    del critical_env  # To avoid All model fields require a type annotation
    del name  # To avoid All model fields require a type annotation

    logger.info(
        "Database URL: "
        f"{database.postgres_user}:<PASSWORD>@"
        f"{database.host}:{database.port}/{database.postgres_database}"
    )

    @property
    def sqlalchemy_async_database_url(self) -> str:
        """Constructs SQLAlchemy URL based on database configuration."""
        if self.database.sqlitedb_path:
            return f"sqlite+aiosqlite:///{self.database.sqlitedb_path}"
        if self.database.host:
            return str(self.database.url)
        return ""

    @property
    def sqlalchemy_database_url(self) -> str:
        """Constructs SQLAlchemy URL based on database configuration."""
        if self.database.sqlitedb_path:
            return f"sqlite:///{self.database.sqlitedb_path}"
        if self.database.host:
            password = self.database.postgres_password.get_secret_value()
            return f"postgresql://{self.database.postgres_user}:{password}@{self.database.host}:{self.database.port}/{self.database.postgres_database}"
        return ""

    @property
    def sqlalchemy_async_database_url_masked(self) -> str:
        """Constructs SQLAlchemy URL based on database configuration."""
        if self.database.sqlitedb_path:
            return f"sqlite+aiosqlite:///{self.database.sqlitedb_path}"
        if self.database.host:
            return f"postgresql+asyncpg://{self.database.postgres_user}:<PASSWORD>@{self.database.host}:{self.database.port}/{self.database.postgres_database}"
        return ""

    @property
    def sqlalchemy_database_url_masked(self) -> str:
        """Constructs SQLAlchemy URL based on database configuration."""
        if self.database.sqlitedb_path:
            return f"sqlite:///{self.database.sqlitedb_path}"
        if self.database.host:
            return f"postgresql://{self.database.postgres_user}:<PASSWORD>@{self.database.host}:{self.database.port}/{self.database.postgres_database}"
        return ""


settings = Settings()
