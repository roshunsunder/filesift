from pathlib import Path
from platformdirs import user_config_dir
import tomllib
from importlib import resources
import tomli_w

APP_NAME = "filesift"


def _merge_configs(defaults: dict, overrides: dict) -> dict:
    """Deep-merge overrides into defaults.

    Only keys present in *defaults* are kept, so removed v0.1 sections
    (like [llm], [api_keys]) in user configs are silently ignored.
    """
    merged = {}
    for key, default_val in defaults.items():
        if key not in overrides:
            merged[key] = default_val
        elif isinstance(default_val, dict) and isinstance(overrides[key], dict):
            merged[key] = _merge_configs(default_val, overrides[key])
        else:
            merged[key] = overrides[key]
    return merged


def get_default_config() -> dict:
    """Load and return the default configuration structure."""
    text = resources.files("filesift._config").joinpath("default_config.toml").read_text()
    return tomllib.loads(text)


def load_config() -> dict:
    """Load config from user config directory, merged with defaults."""
    config_dir = Path(user_config_dir(APP_NAME))
    config_file = config_dir / "config.toml"

    if not config_dir.exists():
        config_dir.mkdir(parents=True)

    defaults = get_default_config()

    if not config_file.exists():
        text = resources.files("filesift._config").joinpath("default_config.toml").read_text()
        config_file.write_text(text)
        return dict(defaults)

    user_config = tomllib.loads(config_file.read_text())
    return _merge_configs(defaults, user_config)


def save_config(config: dict) -> None:
    """Save configuration dictionary to TOML file."""
    config_dir = Path(user_config_dir(APP_NAME))
    config_file = config_dir / "config.toml"
    config_dir.mkdir(parents=True, exist_ok=True)

    with open(config_file, "wb") as f:
        tomli_w.dump(config, f)


config_dict = load_config()
