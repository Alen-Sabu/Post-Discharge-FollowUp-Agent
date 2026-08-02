from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str
    database_url: str

    calle_api_key: str
    calle_base_url: str
    calle_webhook_secret: str | None = None
    calle_webhook_url: str | None = None
    calle_example_phone: str | None = None

    dry_run_default: bool

    anthropic_api_key: str | None = None
    llm_model: str = "claude-sonnet-4-20250514"
    llm_enabled: bool = True

    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from_number: str | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_username: str | None = None
    smtp_password: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @field_validator(
        "calle_webhook_secret",
        "calle_webhook_url",
        "calle_example_phone",
        "anthropic_api_key",
        "twilio_account_sid",
        "twilio_auth_token",
        "twilio_from_number",
        "smtp_host",
        "smtp_port",
        "smtp_username",
        "smtp_password",
        mode="before",
    )
    @classmethod
    def empty_str_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value


settings = Settings()
