from pathlib import Path
from platformdirs import user_config_dir
import tomllib

APP_NAME = "filesift"

def load_config():
    config_dir = Path(user_config_dir(APP_NAME))
    config_file = config_dir / "config.toml"

    # Create dir if missing
    if not config_dir.exists():
        config_dir.mkdir(parents=True)

    # If config file is missing, write default
    if not config_file.exists():
        default_config_path = Path(__file__).parent / "default_config.toml"
        default_config = default_config_path.read_text()
        config_file.write_text(default_config)

    return tomllib.loads(config_file.read_text())

config_dict = load_config()