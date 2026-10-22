import asyncio

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import Permission, Role, User, UserRole
from app.db.session import SessionLocal, dispose_engine

DEV_ISSUER = "http://localhost:8080/realms/ida"
DEV_SUBJECT = "00000000-0000-0000-0000-000000000028"
DEV_EMAIL = "developer@example.local"
DEV_DISPLAY_NAME = "IDA Local Developer"
DEMO_RESOURCES = (
    "analytics.demo_orders",
    "analytics.demo_order_items",
    "analytics.demo_products",
    "analytics.demo_regions",
)


async def provision_dev_oidc_user() -> None:
    settings = get_settings()
    if settings.environment.casefold() != "development" or settings.oidc_issuer != DEV_ISSUER:
        raise RuntimeError(
            "Refusing to provision the local OIDC user outside the configured development realm"
        )

    async with SessionLocal() as session:
        user = await session.scalar(
            select(User).where(
                User.identity_issuer == DEV_ISSUER,
                User.identity_subject == DEV_SUBJECT,
            )
        )
        if user is None:
            email_owner = await session.scalar(select(User).where(User.email == DEV_EMAIL))
            if email_owner is not None:
                raise RuntimeError(
                    "The development email already belongs to another user; refusing to link it"
                )
            user = User(
                email=DEV_EMAIL,
                display_name=DEV_DISPLAY_NAME,
                identity_issuer=DEV_ISSUER,
                identity_subject=DEV_SUBJECT,
                is_active=True,
            )
            session.add(user)
            await session.flush()
        elif not user.is_active:
            raise RuntimeError("The local OIDC user is disabled; enable it explicitly before use")

        analyst = await session.scalar(select(Role).where(Role.name == "analyst"))
        if analyst is None:
            analyst = Role(name="analyst", description="Read-only analytics user")
            session.add(analyst)
            await session.flush()

        role_link = await session.scalar(
            select(UserRole).where(
                UserRole.user_id == user.id,
                UserRole.role_id == analyst.id,
            )
        )
        if role_link is None:
            session.add(UserRole(user_id=user.id, role_id=analyst.id))

        for resource in DEMO_RESOURCES:
            permission = await session.scalar(
                select(Permission).where(
                    Permission.role_id == analyst.id,
                    Permission.resource == resource,
                    Permission.action == "read",
                )
            )
            if permission is None:
                session.add(
                    Permission(
                        role_id=analyst.id,
                        resource=resource,
                        action="read",
                        row_filter=None,
                        column_masks={},
                    )
                )
        await session.commit()


async def main() -> None:
    try:
        await provision_dev_oidc_user()
    finally:
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
