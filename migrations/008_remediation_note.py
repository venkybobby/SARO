"""Migration 008: add remediation_note column to audit_traces."""
from database import engine
from sqlalchemy import text


def upgrade():
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE audit_traces ADD COLUMN IF NOT EXISTS remediation_note TEXT"))
        conn.commit()


if __name__ == "__main__":
    upgrade()
    print("Migration 008 applied: remediation_note column added")
