import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

log = logging.getLogger(__name__)

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
        log.info(f"Inventory already has {result} agents — skipping seed")
        return

    from data.agents import AGENTS
    log.info(f"Seeding {len(AGENTS)} agents into inventory...")

    for agent in AGENTS:
        db.execute(text("""
            INSERT INTO inventory (
                id, name, intent_type, activity, about, location_raw, is_active
            ) VALUES (
                gen_random_uuid(),
                :name,
                :intent_type,
                :activity,
                :about,
                :location_raw,
                true
            )
        """), {
            "name": agent["name"],
            "intent_type": agent["intent_type"],
            "activity": agent["activity"],
            "about": agent["about"],
            "location_raw": agent["location_raw"],
        })

    db.commit()
    log.info("Seeding complete")


def log_activity(db, owner_id, mandate_id, event_type, payload):
    import json
    db.execute(text("""
        INSERT INTO activity_log (owner_id, mandate_id, event_type, payload)
        VALUES (:owner_id, :mandate_id, :event_type, :payload::jsonb)
    """), {
        "owner_id": owner_id,
        "mandate_id": mandate_id,
        "event_type": event_type,
        "payload": json.dumps(payload)
    })
    db.commit()
