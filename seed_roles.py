
from sqlalchemy import select

from app.database.session import SessionLocal
from app.models import Role


DEFAULT_ROLES = [
    {
        "name": "super_admin",
        "description": "Full system access and administration",
    },
    {
        "name": "admin",
        "description": "Platform administration",
    },
    {
        "name": "support_agent",
        "description": "Customer support and transaction assistance",
    },
    {
        "name": "customer",
        "description": "Customer wallet and transaction access",
    },
]


def seed_roles() -> None:
    with SessionLocal() as db:
        try:
            for role_data in DEFAULT_ROLES:
                existing_role = db.scalar(
                    select(Role).where(Role.name == role_data["name"])
                )

                if existing_role is None:
                    db.add(Role(**role_data))
                    print(f"Created role: {role_data['name']}")
                else:
                    print(f"Role already exists: {role_data['name']}")

            db.commit()
            print("Role seeding completed successfully.")

        except Exception:
            db.rollback()
            raise


if __name__ == "__main__":
    seed_roles()
