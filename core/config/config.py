import json
from pathlib import Path


def load_config_file() -> dict:
    root_dir: Path = Path(__file__).parent.parent.parent
    config_file: Path = root_dir / "config.json"
    if not config_file.exists():
        raise FileNotFoundError(f"Cannot find the config file: {config_file}")
    with config_file.open("r") as f:
        return json.load(f)
