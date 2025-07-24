import os
import sys
from pathlib import Path

if base_dir := os.environ.get("YTP_CONFIG_PATH"):
    base_dir = Path(base_dir)
    user_site = base_dir / f"python{sys.version_info.major}.{sys.version_info.minor}-packages"

    if not user_site.exists():
        user_site.mkdir(parents=True, exist_ok=True)

    if user_site.is_dir() and str(user_site) not in sys.path:
        sys.path.insert(0, str(user_site))
