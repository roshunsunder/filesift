from pathlib import Path
from platformdirs import user_config_dir
import tomllib
from importlib import resources
import tomli_w

APP_NAME = "filesift"

def load_config():
    config_dir = Path(user_config_dir(APP_NAME))
    config_file = config_dir / "config.toml"

    if not config_dir.exists():
        config_dir.mkdir(parents=True)

    if not config_file.exists():
        default_config = resources.files("filesift._config").joinpath("default_config.toml").read_text()
        config_file.write_text(default_config)

    return tomllib.loads(config_file.read_text())

def save_config(config: dict):
    """Save configuration dictionary to TOML file"""
    config_dir = Path(user_config_dir(APP_NAME))
    config_file = config_dir / "config.toml"
    
    config_dir.mkdir(parents=True, exist_ok=True)
    
    with open(config_file, "wb") as f:
        tomli_w.dump(config, f)

def get_default_config():
    """Load and return the default configuration structure"""
    default_config_text = resources.files("filesift._config").joinpath("default_config.toml").read_text()
    return tomllib.loads(default_config_text)

config_dict = load_config()