import os

from dotenv import load_dotenv

load_dotenv()

DB_USER = os.getenv("DB_USER", "admin")
DB_PASSWORD = os.getenv("ADMIN_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "data_mesh_plt")
DB_SSL_MODE = os.getenv("DB_SSL_MODE", "require")

_raw_cors = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
CORS_ORIGINS = [o.strip() for o in _raw_cors.split(",") if o.strip()]

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "15")
)
JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "GuhBrando/dmplt-data-contract")

# GitHub App (preferred over GITHUB_TOKEN once all three are set). The App's
# private key stays in Azure Key Vault; only its versionless key identifier is
# configured here, e.g. https://dmplt-kv.vault.azure.net/keys/github-app
GITHUB_APP_CLIENT_ID = os.getenv("GITHUB_APP_CLIENT_ID", "")
GITHUB_APP_INSTALLATION_ID = os.getenv("GITHUB_APP_INSTALLATION_ID", "")
GITHUB_APP_KEY_VAULT_KEY_ID = os.getenv("GITHUB_APP_KEY_VAULT_KEY_ID", "")
