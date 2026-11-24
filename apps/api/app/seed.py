"""Dados iniciais idempotentes. Uso: python -m app.seed"""

import asyncio

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine, get_sessionmaker
from app.modules.groups.models import GroupTheme

THEMES = [
    {
        "slug": "amigo-secreto",
        "display_name": "Amigo Secreto",
        "emoji": "🎁",
        "description": "O clássico: cada um tira um nome e presenteia em segredo.",
    },
    {
        "slug": "amigo-da-onca",
        "display_name": "Amigo da Onça",
        "emoji": "🐆",
        "description": "Vale presente engraçado, inútil ou duvidoso. Quanto pior, melhor!",
    },
    {
        "slug": "amigo-calcinha",
        "display_name": "Amigo Calcinha",
        "emoji": "🩲",
        "description": "Todo mundo presenteia com uma peça íntima (com bom humor e respeito).",
    },
]


async def seed_themes(session: AsyncSession) -> None:
    stmt = insert(GroupTheme).values(THEMES)
    stmt = stmt.on_conflict_do_update(
        index_elements=[GroupTheme.slug],
        set_={
            "display_name": stmt.excluded.display_name,
            "emoji": stmt.excluded.emoji,
            "description": stmt.excluded.description,
        },
    )
    await session.execute(stmt)
    await session.commit()


async def main() -> None:
    async with get_sessionmaker()() as session:
        await seed_themes(session)
    await get_engine().dispose()
    print(f"seed ok: {len(THEMES)} temas")


if __name__ == "__main__":
    asyncio.run(main())
