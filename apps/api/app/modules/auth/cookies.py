from fastapi import Response

from app.core.config import get_settings
from app.core.security import generate_token
from app.modules.auth.service import TokenPair

ACCESS_COOKIE = "tv_access"
REFRESH_COOKIE = "tv_refresh"
CSRF_COOKIE = "tv_csrf"
CSRF_HEADER = "X-CSRF-Token"

ACCESS_PATH = "/api"
REFRESH_PATH = "/api/v1/auth"


def set_auth_cookies(response: Response, tokens: TokenPair) -> None:
    settings = get_settings()
    common = {"secure": settings.cookie_secure, "samesite": "lax", "domain": settings.cookie_domain}
    response.set_cookie(
        ACCESS_COOKIE,
        tokens.access_token,
        max_age=settings.access_token_ttl_minutes * 60,
        path=ACCESS_PATH,
        httponly=True,
        **common,  # type: ignore[arg-type]
    )
    response.set_cookie(
        REFRESH_COOKIE,
        tokens.refresh_token,
        expires=tokens.refresh_expires_at,
        path=REFRESH_PATH,
        httponly=True,
        **common,  # type: ignore[arg-type]
    )
    set_csrf_cookie(response)


def set_csrf_cookie(response: Response, token: str | None = None) -> str:
    """Cookie legível pelo JS (double-submit): o front reenvia o valor no header X-CSRF-Token."""
    settings = get_settings()
    value = token or generate_token()
    response.set_cookie(
        CSRF_COOKIE,
        value,
        max_age=settings.refresh_token_ttl_days * 86400,
        path="/",
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        domain=settings.cookie_domain,
    )
    return value


def clear_auth_cookies(response: Response) -> None:
    settings = get_settings()
    for name, path in ((ACCESS_COOKIE, ACCESS_PATH), (REFRESH_COOKIE, REFRESH_PATH)):
        response.delete_cookie(
            name,
            path=path,
            domain=settings.cookie_domain,
            secure=settings.cookie_secure,
            httponly=True,
            samesite="lax",
        )
