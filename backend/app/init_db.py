"""Create all tables against the configured database. Run once to bootstrap."""
from app.db import Base, engine
import app.models  # noqa: F401  注册所有模型


def main() -> None:
    Base.metadata.create_all(engine)
    print(f"tables created: {sorted(Base.metadata.tables)}")


if __name__ == "__main__":
    main()
