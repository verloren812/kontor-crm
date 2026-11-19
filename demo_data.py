"""
Demo data for the public live demo and for local development.

Usage:
    python demo_data.py            # add demo data to an empty database
    python demo_data.py --reset    # wipe all data first, then seed

All companies, people, phone numbers and e-mail addresses are fictional
(e-mail domains use the reserved .example TLD).
"""
import argparse
import random
from datetime import timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

import models
import security
from enums import ClientStatus, DealStage, Role

DEMO_ACCOUNTS = [
    {"username": "demo-admin", "password": "demo-admin-2026", "role": Role.ADMIN.value},
    {"username": "anna", "password": "demo-anna-2026", "role": Role.MANAGER.value},
    {"username": "jonas", "password": "demo-jonas-2026", "role": Role.MANAGER.value},
]

COMPANIES = [
    ("Nordlicht Logistik GmbH", "nordlicht-logistik"),
    ("Bäckerei Sonnenkorn", "sonnenkorn"),
    ("Weserblick Immobilien", "weserblick"),
    ("Hansen & Partner Steuerberatung", "hansen-partner"),
    ("Grünwerk Gartenbau", "gruenwerk"),
    ("Kaltenbach Maschinenbau AG", "kaltenbach"),
    ("Café Lindenhof", "lindenhof"),
    ("Brückner IT-Service", "brueckner-it"),
    ("Möbelhaus Eichenwald", "eichenwald"),
    ("Autohaus Steinmeier", "steinmeier"),
    ("Praxis Dr. Vogt", "praxis-vogt"),
    ("Fahrschule Kurvenreich", "kurvenreich"),
    ("Elbe Event Catering", "elbe-catering"),
    ("Holzwerkstatt Bergmann", "bergmann-holz"),
    ("Sportstudio Kraftwerk", "kraftwerk-sport"),
    ("Druckerei Lettermann", "lettermann"),
    ("Hotel Am Schlosspark", "schlosspark-hotel"),
    ("Solartechnik Morgenrot", "morgenrot-solar"),
]

DEAL_TITLES = [
    "Website relaunch", "Annual maintenance contract", "Online booking system",
    "Customer portal", "Inventory management", "Newsletter integration",
    "Online shop", "Support package 2027", "Data migration", "Mobile app MVP",
    "Reporting dashboard", "Hosting & backups", "SEO package", "Staff training",
]

TASK_TITLES = [
    "Call back about the offer", "Send updated proposal", "Prepare demo",
    "Clarify requirements", "Schedule kick-off meeting", "Send contract draft",
    "Follow up on invoice", "Collect feedback", "Check budget with client",
]

# How many deals end up in each stage: a realistic funnel, wide at the top.
STAGE_WEIGHTS = {
    DealStage.NEW: 6,
    DealStage.QUALIFIED: 5,
    DealStage.PROPOSAL: 4,
    DealStage.NEGOTIATION: 3,
    DealStage.WON: 5,
    DealStage.LOST: 3,
}


def reset(db: Session) -> None:
    """Delete every row, children first."""
    for model in (models.Task, models.DealStageChange, models.Deal, models.Client, models.User):
        db.query(model).delete()
    db.commit()


def seed(db: Session, rng_seed: int = 42) -> None:
    rng = random.Random(rng_seed)  # fixed seed: the demo looks the same after every reset
    now = models.utcnow()

    users = []
    for account in DEMO_ACCOUNTS:
        user = models.User(
            username=account["username"],
            hashed_password=security.get_password_hash(account["password"]),
            role=account["role"],
        )
        db.add(user)
        users.append(user)
    db.flush()
    managers = [u for u in users if u.role == Role.MANAGER.value]

    stages = [stage for stage, weight in STAGE_WEIGHTS.items() for _ in range(weight)]
    rng.shuffle(stages)

    for index, (company, domain) in enumerate(COMPANIES):
        owner = managers[index % len(managers)] if index % 7 else None  # a few unassigned
        client = models.Client(
            name=company,
            phone=f"+4915100{index + 1:06d}",
            email=f"info@{domain}.example",
            status=rng.choice(list(ClientStatus)).value,
            owner_id=owner.id if owner else None,
            created_at=now - timedelta(days=rng.randint(20, 200)),
        )
        db.add(client)
        db.flush()

        for _ in range(rng.randint(0, 2) + (1 if stages else 0)):
            if not stages:
                break
            stage = stages.pop()
            created = now - timedelta(days=rng.randint(5, 120))
            deal = models.Deal(
                title=rng.choice(DEAL_TITLES),
                amount=Decimal(rng.randrange(800, 48000, 50)),
                stage=stage.value,
                client_id=client.id,
                owner_id=client.owner_id,
                created_at=created,
            )
            # Walk the deal through the pipeline so the stage history is realistic.
            path = [DealStage.NEW]
            order = [DealStage.NEW, DealStage.QUALIFIED, DealStage.PROPOSAL, DealStage.NEGOTIATION]
            if stage in order:
                path = order[: order.index(stage) + 1]
            else:
                path = order[: rng.randint(2, 4)] + [stage]
            moment = created
            previous = None
            for step in path:
                deal.stage_history.append(
                    models.DealStageChange(
                        from_stage=previous.value if previous else None,
                        to_stage=step.value,
                        changed_at=moment,
                        changed_by_id=client.owner_id,
                    )
                )
                previous = step
                moment += timedelta(days=rng.randint(2, 12))
            db.add(deal)
            db.flush()

            if not stage.is_closed:
                for _ in range(rng.randint(1, 2)):
                    db.add(
                        models.Task(
                            title=rng.choice(TASK_TITLES),
                            due_date=now + timedelta(days=rng.randint(-6, 14), hours=rng.randint(0, 8)),
                            is_done=rng.random() < 0.2,
                            deal_id=deal.id,
                        )
                    )
    db.commit()


if __name__ == "__main__":
    from database import SessionLocal

    parser = argparse.ArgumentParser(description="Fill the database with demo data.")
    parser.add_argument("--reset", action="store_true", help="delete all existing data first")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        if args.reset:
            reset(session)
        elif session.query(models.User).count():
            raise SystemExit("The database is not empty. Use --reset to replace its contents.")
        seed(session)
        print("Demo data created. Logins:")
        for account in DEMO_ACCOUNTS:
            print(f"  {account['username']:<12} {account['password']:<18} ({account['role']})")
    finally:
        session.close()
