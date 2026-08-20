from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class APIAuthSettings(BaseSettings):
    """API authentication settings."""

    model_config = SettingsConfigDict(
        env_prefix="APX_API_",
        case_sensitive=False,
        extra="ignore",
    )

    # API Keys for different roles
    # Format: "key:role" or use separate keys per role
    api_keys: str = Field(
        default="",
        description="Comma-separated list of API keys with roles: key1:role1,key2:role2",
    )

    # Header name for API key
    api_key_header: str = Field(default="X-API-Key")

    def get_keys_with_roles(self) -> dict[str, str]:
        """Parse API keys with roles."""
        result = {}
        if not self.api_keys:
            return result
        for item in self.api_keys.split(","):
            item = item.strip()
            if ":" in item:
                key, role = item.split(":", 1)
                result[key.strip()] = role.strip()
            else:
                # Default to reader if no role specified
                result[item] = "reader"
        return result


class APISettings(BaseSettings):
    """API application settings."""

    model_config = SettingsConfigDict(
        env_prefix="APX_API_",
        case_sensitive=False,
        extra="ignore",
    )

    # Application settings
    title: str = Field(default="APX - Autonomous Accounts Payable Exception Resolution Agent")
    version: str = Field(default="0.4.0")
    description: str = Field(default="APX API for invoice exception resolution")
    debug: bool = Field(default=False)

    # Server settings
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)

    # CORS settings
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    cors_allow_credentials: bool = Field(default=False)
    cors_allow_methods: list[str] = Field(default_factory=lambda: ["*"])
    cors_allow_headers: list[str] = Field(default_factory=lambda: ["*"])

    # Request/response settings
    request_id_header: str = Field(default="X-Request-ID")
    correlation_id_header: str = Field(default="X-Correlation-ID")
    max_request_size: int = Field(default=10_485_760)  # 10MB

    # Rate limiting (simple in-memory)
    rate_limit_enabled: bool = Field(default=True)
    rate_limit_requests_per_minute: int = Field(default=60)

    # Auth settings
    auth: APIAuthSettings = Field(default_factory=APIAuthSettings)

    # Observability
    log_requests: bool = Field(default=True)
    log_request_body: bool = Field(default=False)
    log_response_body: bool = Field(default=False)


# Global settings instance
_api_settings: Optional[APISettings] = None


def get_api_settings() -> APISettings:
    """Get or create the global API settings."""
    global _api_settings
    if _api_settings is None:
        _api_settings = APISettings()
    return _api_settings


def reset_api_settings() -> None:
    """Reset the global API settings."""
    global _api_settings
    _api_settings = None