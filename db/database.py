import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def seed_inventory(db):
    result = db.execute(text("SELECT COUNT(*) FROM inventory")).scalar()
    if result > 0:
        return

    from data.agents import AGENTS
    for agent in AGENTS:
        db.execute(text("""
            INSERT INTO inventory (id, name, category, vertical, mandate, is_active)
            VALUES (gen_random_uuid(), :name, :category, :vertical, :mandate, true)
        """), {
            "name": agent["name"],
            "category": agent["category"],
            "vertical": agent.get("vertical", "services"),
            "mandate": agent["mandate"],
        })
    db.commit()


def log_activity(db, owner_id, mandate_id, event_type, payload):
    db.execute(text("""
        INSERT INTO activity_log (owner_id, mandate_id, event_type, payload)
        VALUES (:owner_id, :mandate_id, :event_type, :payload::jsonb)
    """), {
        "owner_id": owner_id,
        "mandate_id": mandate_id,
        "event_type": event_type,
        "payload": __import__("json").dumps(payload)
    })
    db.commit()
