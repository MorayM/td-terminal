"""Configuration loader for Todoist CLI.

Manually parses .env file to load API token without external dependencies.
"""

from pathlib import Path


class ConfigError(Exception):
    """Raised when configuration is invalid or missing."""

    pass


def load_config() -> dict:
    """Load configuration from .env file.

    Returns:
        dict with 'api_key' field

    Raises:
        ConfigError: If .env file missing or TODOIST_API_KEY not set
    """
    env_path = Path(__file__).parent / ".env"

    if not env_path.exists():
        raise ConfigError(f".env file not found at {env_path}")

    config = {}

    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                config[key.strip()] = value.strip()

    if "TODOIST_API_KEY" not in config:
        raise ConfigError("TODOIST_API_KEY not found in .env file")

    if not config["TODOIST_API_KEY"]:
        raise ConfigError("TODOIST_API_KEY is empty in .env file")

    return {"api_key": config["TODOIST_API_KEY"]}
