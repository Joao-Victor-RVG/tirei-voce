"""Concede ou remove acesso de admin. Uso: python -m app.admin grant|revoke <email>"""

import asyncio
import sys

from app.core.db import get_engine, get_sessionmaker
from app.modules.users.repository import UserRepository


async def main(action: str, email: str) -> int:
    async with get_sessionmaker()() as session:
        user = await UserRepository(session).get_by_email(email)
        if user is None:
            print(f"usuário não encontrado: {email}")
            return 1
        user.is_admin = action == "grant"
        await session.commit()
    await get_engine().dispose()
    print(f"{email}: is_admin={action == 'grant'}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("grant", "revoke"):
        print("uso: python -m app.admin grant|revoke <email>")
        sys.exit(2)
    sys.exit(asyncio.run(main(sys.argv[1], sys.argv[2])))
