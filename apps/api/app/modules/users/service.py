from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import UnprocessableError
from app.modules.notifications.whatsapp import normalize_br_phone
from app.modules.users.models import User
from app.modules.users.schemas import MeUpdate


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def update_me(self, user: User, data: MeUpdate) -> User:
        changes = data.model_dump(exclude_unset=True)
        for flag in ("email_reminders", "whatsapp_opt_in"):
            if flag in changes and changes[flag] is None:
                changes.pop(flag)
        if "phone" in changes:
            raw = changes["phone"]
            if raw:
                phone = normalize_br_phone(raw)
                if phone is None:
                    raise UnprocessableError(
                        "Informe um celular válido com DDD, ex.: (11) 98765-4321.",
                        code="invalid_phone",
                    )
                changes["phone"] = phone
            else:
                changes["phone"] = None
                changes["whatsapp_opt_in"] = False
        phone_after = changes.get("phone", user.phone)
        if changes.get("whatsapp_opt_in") and not phone_after:
            raise UnprocessableError(
                "Informe seu celular para receber avisos pelo WhatsApp.", code="phone_required"
            )
        if "name" in changes and changes["name"] is None:
            raise UnprocessableError("O nome não pode ficar vazio.", code="name_required")
        for field, value in changes.items():
            setattr(user, field, str(value) if field == "avatar_url" and value else value)
        await self.session.commit()
        await self.session.refresh(user)
        return user
