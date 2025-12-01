from pathlib import Path
from platformdirs import user_config_dir
import tomllib
from importlib import resources

APP_NAME = "filesift"

def load_config():
    config_dir = Path(user_config_dir(APP_NAME))
    config_file = config_dir / "config.toml"

    # Create dir if missing
    if not config_dir.exists():
        config_dir.mkdir(parents=True)

    # If config file is missing, write default
    if not config_file.exists():
        default_config = resources.files("filesift._config").joinpath("default_config.toml").read_text()
        config_file.write_text(default_config)

    return tomllib.loads(config_file.read_text())

config_dict = load_config()