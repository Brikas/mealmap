from typing import Any

from pydantic_settings import BaseSettings as PydanticBaseSettings


class BaseSettings(PydanticBaseSettings):
    """
    Base settings class that inherits from PydanticBaseSettings.

    How it works:
    1. Pydantic automatically reads environment variables that match the field names.
    2. It applies the `env_prefix` defined in the inner `Config` class.
       For example, if `env_prefix="MY_"`, a field named `host` will be populated
       by the environment variable `MY_HOST`.
    3. It also loads variables from the `.env` file specified in `env_file`.
    4. Type conversion is automatic (e.g., "true" in env var becomes `True` boolean).
    """

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
