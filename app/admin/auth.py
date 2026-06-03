import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.config import settings

security = HTTPBasic()


def require_admin(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    if not settings.ADMIN_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin panel not configured (set ADMIN_PASSWORD)",
        )
    ok_user = secrets.compare_digest(
        credentials.username.encode(), settings.ADMIN_USERNAME.encode()
    )
    ok_pass = secrets.compare_digest(
        credentials.password.encode(), settings.ADMIN_PASSWORD.encode()
    )
    if not (ok_user and ok_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username
