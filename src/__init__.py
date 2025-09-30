from pathlib import Path
import yaml

# ROOT
ROOT_DIR = Path(__file__).resolve().parent.parent

# reading config
with open(ROOT_DIR / "config" / "config.yaml", "r", encoding="utf-8") as f:
    _conf = yaml.safe_load(f)

# adding relative paths
raw_path = (ROOT_DIR / _conf["files"]["raw_path"]).resolve()
wip_path = (ROOT_DIR / _conf["files"]["wip_path"]).resolve()
done_path = (ROOT_DIR / _conf["files"]["done_path"]).resolve()