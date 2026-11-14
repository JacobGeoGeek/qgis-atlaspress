import base64
import json
from pathlib import Path


def is_server_key(value: str) -> bool:
    """Reject server credentials; decoding here does not authenticate a user."""
    if value.startswith("sb_secret_"):
        return True
    try:
        payload = value.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        return isinstance(claims, dict) and claims.get("role") == "service_role"
    except (ValueError, IndexError, UnicodeDecodeError):
        return False


def get_config_path() -> Path:
    root_dir: Path = Path(__file__).parent.parent.parent
    return root_dir / "config.json"


def load_config_file(path: Path | None = None) -> dict:
    config_file = path if path is not None else get_config_path()
    if not config_file.exists():
        raise FileNotFoundError(f"Cannot find the config file: {config_file}")

    with config_file.open("r") as f:
        return json.load(f)
