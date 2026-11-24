from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import UnprocessableError
from app.modules.notifications.models import PushSubscription
from app.modules.notifications.push import is_allowed_endpoint
from app.modules.notifications.schemas import PushConfigOut, PushSubscriptionIn
from app.modules.users.models import User


class PushSubscriptionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def config(self, user: User, endpoint: str | None) -> PushConfigOut:
        settings = get_settings()
        subscribed = False
        if endpoint:
            found = await self.session.scalar(
                select(PushSubscription.id).where(
                    PushSubscription.endpoint == endpoint, PushSubscription.user_id == user.id
                )
            )
            subscribed = found is not None
        return PushConfigOut(
            enabled=settings.push_enabled,
            public_key=settings.vapid_public_key if settings.push_enabled else None,
            subscribed=subscribed,
        )

    async def subscribe(self, user: User, data: PushSubscriptionIn, user_agent: str | None) -> None:
        endpoint = str(data.endpoint)
        if not is_allowed_endpoint(endpoint):
            raise UnprocessableError(
                "Este navegador usa um serviço de notificações não suportado.",
                code="push_endpoint_not_allowed",
            )
        existing = await self.session.scalar(
            select(PushSubscription).where(PushSubscription.endpoint == endpoint)
        )
        if existing is None:
            self.session.add(
                PushSubscription(
                    user_id=user.id,
                    endpoint=endpoint,
                    p256dh=data.keys.p256dh,
                    auth=data.keys.auth,
                    user_agent=(user_agent or "")[:512] or None,
                )
            )
        else:  # mesmo navegador: atualiza as chaves e passa a ser de quem está logado agora
            existing.user_id = user.id
            existing.p256dh = data.keys.p256dh
            existing.auth = data.keys.auth
        await self.session.commit()

    async def unsubscribe(self, user: User, endpoint: str) -> None:
        await self.session.execute(
            delete(PushSubscription).where(
                PushSubscription.endpoint == endpoint, PushSubscription.user_id == user.id
            )
        )
        await self.session.commit()
