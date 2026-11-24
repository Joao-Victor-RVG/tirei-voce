from functools import lru_cache
from pathlib import Path

from app.core.errors import UnprocessableError

MIN_LENGTH = 8
MAX_LENGTH = 128


@lru_cache
def _common_passwords() -> frozenset[str]:
    path = Path(__file__).with_name("common_passwords.txt")
    lines = path.read_text(encoding="utf-8").splitlines()
    return frozenset(line.strip().lower() for line in lines if line.strip())


def validate_password(password: str, *, email: str | None = None) -> None:
    if len(password) < MIN_LENGTH:
        raise UnprocessableError(
            f"A senha precisa ter pelo menos {MIN_LENGTH} caracteres.", code="weak_password"
        )
    if len(password) > MAX_LENGTH:
        raise UnprocessableError(
            f"A senha pode ter no máximo {MAX_LENGTH} caracteres.", code="weak_password"
        )
    lowered = password.lower()
    if lowered in _common_passwords() or len(set(password)) < 3:
        raise UnprocessableError(
            "Essa senha é muito comum e fácil de adivinhar. Escolha outra.", code="weak_password"
        )
    if email and lowered == email.strip().lower():
        raise UnprocessableError("A senha não pode ser igual ao e-mail.", code="weak_password")
