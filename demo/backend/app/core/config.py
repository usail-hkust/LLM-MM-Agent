"""
Configuration management using Pydantic Settings.

Centralizes all configuration from environment variables with sensible defaults.
"""
from typing import List, Union
from pydantic import AnyHttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Identity
    PROJECT_NAME: str = "MM-Agent Open Local Service"
    API_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    OPEN_SOURCE_LOCAL_MODE: bool = True
    
    # Security
    SECRET_KEY: str = "dev_secret_key_change_me_in_production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    ALGORITHM: str = "HS256"
    CORS_ORIGINS: List[Union[str, AnyHttpUrl]] = ["*"]
    
    # Local Auth Defaults
    ALLOW_PUBLIC_REGISTRATION: bool = True
    REQUIRE_INVITE_CODE: bool = False
    SEED_LOCAL_ADMIN: bool = True
    LOCAL_ADMIN_EMAIL: str = "admin@local.dev"
    LOCAL_ADMIN_PASSWORD: str = "admin12345"

    # Infrastructure
    DATABASE_URL: str = "sqlite+aiosqlite:///./runtime/mmagent.db"
    
    # Redis Configuration
    REDIS_URL: str = ""  # Optional. Leave empty for local single-process mode.
    REDIS_PREFIX: str = "lcp:v1"  # Namespace prefix for key isolation
    REDIS_STREAM_MAX_LEN: int = 2000  # Maximum length for Redis Streams
    
    # [FIX] Database Pool Tuning
    # Adjust based on Pod CPU/Worker count.
    # Default: 20 connections + 10 overflow. Recycle every hour.
    DB_POOL_SIZE: int = 50
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE: int = 3600

    STORAGE_ROOT: str = "runtime/storage/blobs"
    TEMPLATE_ROOT: str = "app/templates"  # Relative to backend/ directory
    
    # External API Keys (Inject via Environment)
    OPENAI_API_KEY: str = ""
    E2B_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    TAVILY_API_KEY: str = ""
    
    # --- E2B Configuration (Architecture v3.0) ---
    # The alias to use for the custom environment
    E2B_TEMPLATE_ALIAS: str = "lcp-paper-agent-v3"
    # Base template to extend (Official E2B Code Interpreter)
    E2B_BASE_TEMPLATE: str = "code-interpreter-v1"
    # Metadata key used to tag sandboxes with project IDs for stateless discovery
    E2B_PROJECT_LABEL_KEY: str = "project_id"
    # Python packages to pre-install during build
    E2B_PIP_PACKAGES: List[str] = [
        "pandas",
        "numpy",
        "scipy",
        "scikit-learn",
        "xgboost",
        "lightgbm",
        "statsmodels",
        "patsy",
        "sympy",
        "networkx",
        "cvxpy",
        "ortools",
        "matplotlib",
        "seaborn",
        "plotly",
        "openpyxl",
        "tabulate",
        "pyarrow",
        "requests",
        "beautifulsoup4",
        "tqdm",
        "joblib",
    ]
    # APT packages to pre-install during build (LaTeX toolchain)
    E2B_APT_PACKAGES: List[str] = [
        "texlive-latex-base",
        "texlive-latex-extra",
        "texlive-xetex",
        "texlive-science",
        "texlive-fonts-recommended",
        "latexmk",
        "ripgrep",
        "git",
        "curl",
        "vim",
        "ghostscript",
    ]
    # Node/NPM packages to pre-install during build (for claude-code CLI)
    E2B_NPM_PACKAGES: List[str] = [
        "@anthropic-ai/claude-code@latest",
        "@musistudio/claude-code-router",  # Router middleware for LLM routing
        "csv-parser"
    ]
    # Set to True to force a rebuild on every restart (useful for dev, costly for prod)
    E2B_FORCE_REBUILD: bool = False
    
    # Custom LLM Config (from .env)
    API_KEY: str = ""      # OpenAI-compatible API key for router / direct calls
    BASE_URL: str = "https://api.openai.com/v1"
    MODEL_NAME: str = "gpt-4o-mini"
    AGENT_MODEL_NAME: str = "" # 将被 Router 映射的目标模型 (默认使用 MODEL_NAME)
    
    # Router Configuration Toggle
    # 如果为 True，SandboxGateway 将启动 Router 并劫持 claude 请求
    USE_LLM_ROUTER: bool = True
    
    # [REFACTORED] Infrastructure Retries (Tenacity - Network Layer)
    # These are for API-level retries (500/429 errors), NOT business logic retries.
    # MUST BE PRESERVED - Critical for network stability.
    LLM_RETRY_ATTEMPTS: int = 3
    LLM_RETRY_MIN_WAIT: int = 1
    LLM_RETRY_MAX_WAIT: int = 3
    
    # [REFACTORED] Agent Resource Boundaries
    # Replaces explicit retry counts (AUTO_FIX_RETRIES, COMPILATION_RETRIES).
    # The Agent manages its own loops within this time budget.
    DEFAULT_AGENT_TIMEOUT: int = 3600
    
    # Constraints (Legacy - kept for backward compatibility)
    DEFAULT_TIMEOUT: int = 3600  # Seconds
    
    # Sandbox Lifecycle
    SANDBOX_TIMEOUT: int = 3600
    SANDBOX_EXECUTION_TIMEOUT: int = 3600
    # Remote working directory
    SANDBOX_DATA_DIR: str = "/home/user/workdir"
    SANDBOX_CONNECTION_RETRIES: int = 3

    # System Buffers
    # [FIX] Separate buffers to prevent log flooding from evicting critical state
    EVENT_BUS_HISTORY_SIZE: int = 10        # Critical events (State, Errors)
    EVENT_BUS_LOG_HISTORY_SIZE: int = 50  # High-volume logs (EXEC_LOG)

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    @model_validator(mode="after")
    def set_agent_model_default(self):
        """
        If AGENT_MODEL_NAME is not explicitly set (empty string), 
        default it to MODEL_NAME to ensure compatibility with the provider.
        This fixes the issue where SiliconFlow doesn't support Claude models.
        """
        if not self.AGENT_MODEL_NAME:
            self.AGENT_MODEL_NAME = self.MODEL_NAME
        return self

    model_config = SettingsConfigDict(
        env_file=[".env", "backend/.env", "../.env"], 
        extra="ignore",
        env_file_encoding="utf-8"
    )


settings = Settings()
