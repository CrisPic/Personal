from pathlib import Path
import yaml

# ROOT
ROOT_DIR = Path(__file__).resolve().parent.parent

# reading config
with open(ROOT_DIR / "config" / "config.yaml", "r", encoding="utf-8") as f:
    _conf = yaml.safe_load(f)

# adding relative paths
raw_path = (ROOT_DIR / _conf["files"]["raw_path"]).resolve()
processed_path = (ROOT_DIR / _conf["files"]["processed_path"]).resolve()


# Ensure directories exist
raw_path.mkdir(parents=True, exist_ok=True)
processed_path.mkdir(parents=True, exist_ok=True)