from typing import Any

from pydantic_settings import BaseSettings as PydanticBaseSettings


class BaseSettings(PydanticBaseSettings):
    """Base settings."""

    class Config:
        env_file = ".env"
        env_prefix = "MY_"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def env_vars(self) -> dict[str, Any]:
        """All env variables with default values."""
        env_vars: dict[str, Any] = {}

        def create_env_vars(
            dic: dict[str, Any],
            prefix: str,
            delimiter: str,
        ) -> None:
            """Recursively add env variables to dict."""
            for key, value in dic.items():
                fixed_key = prefix + delimiter + key.upper()

                if isinstance(value, dict):
                    create_env_vars(value, fixed_key, "_")
                else:
                    env_vars[fixed_key] = value

        create_env_vars(self.dict(), self.Config.env_prefix, "")
        return env_vars

    @property
    def env_file_string(self) -> str:
        """Return string for .env file."""
        return "".join(
            f"{key}={value if value is not None else ''}\n"
            for key, value in self.env_vars.items()
        )
