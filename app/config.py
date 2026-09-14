from pathlib import Path


from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):

    # 项目配置类

    project_name: str = "Enterprise Travel Reimbursement Agent"
    debug: bool = True

    database_url: str = (
        f"sqlite:///{BASE_DIR / 'data' / 'reimbursement.db'}"
    )
    rules_markdown_path: str = str(
        BASE_DIR / "data" / "rules" / "company_travel_policy.md"
    )
    policy_rules_path: str = str(
        BASE_DIR / "data" / "rules" / "policy_rules.json"
    )

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        env_prefix="TRAVEL_AGENT_",
        extra="ignore",
    )


settings = Settings()
