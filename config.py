"""Reads settings from the .env file (if it exists) and from the environment."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_env():
    """Very small .env reader so we don't need an extra library."""
    env_path = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            # real environment variables win over the file
            os.environ.setdefault(key.strip(), value.strip())


load_env()

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-please-change")
DATABASE_PATH = os.environ.get("DATABASE_PATH", "studio.db")
if not os.path.isabs(DATABASE_PATH):
    DATABASE_PATH = os.path.join(BASE_DIR, DATABASE_PATH)
