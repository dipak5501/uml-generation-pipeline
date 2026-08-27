#!/usr/bin/env python3
"""Generate ≥200 artifacts into data/uml_app.db for Generated Diagrams UI."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from sqlmodel import Session, select

from app.db import get_engine, init_db
from app.models import UMLArtifact
from app.routers.generate import _load_sample_requirements
from app.services.orchestration import get_or_create_default_project, run_single_generation
from app.settings import get_settings

TYPES = ["class", "object", "component", "package"]
N_REQ = 50  # 50 × 4 = 200 scenario artifacts

SOURCE_SNIPPETS = [
    """public class OrderService {
  private Cart cart;
  public void checkout(User user, PaymentMethod pm) { /* charge and create Order */ }
}""",
    """class Library:
    def __init__(self):
        self.books = []
    def borrow(self, member, book):
        return Loan(member, book)
""",
    """interface PaymentGateway { charge(amount: number): Promise<Receipt>; }
class StripeGateway implements PaymentGateway { charge(amount) { return Promise.resolve({}); } }
""",
    """package com.shop;
public class Product { String sku; double price; }
public class Inventory { void reserve(Product p, int qty); }
""",
    """type User = { id: string; email: string };
type Session = { userId: string; token: string };
function login(email: string, password: string): Session { return { userId: "1", token: "t" }; }
""",
    """public class BankAccount {
  private double balance;
  public void deposit(double a) { balance += a; }
  public boolean withdraw(double a) { if (a>balance) return false; balance-=a; return true; }
}
""",
    """class Sensor { def read(self) -> float: return 0.0 }
class Controller:
    def __init__(self, sensors): self.sensors = sensors
    def poll(self): return [s.read() for s in self.sensors]
""",
    """entity Patient { id, name }
entity Appointment { patient_id, doctor_id, when }
service Scheduler { book(patient, doctor, when) }
""",
]


def main() -> None:
    init_db()
    settings = get_settings().model_copy(update={"max_repair_attempts": 0})
    total = 0
    ok = 0
    with Session(get_engine()) as session:
        project = get_or_create_default_project(session)
        reqs = _load_sample_requirements(N_REQ)
        for req in reqs:
            for dtype in TYPES:
                art = run_single_generation(
                    session,
                    requirement=req,
                    diagram_type=dtype,
                    project_id=project.id,
                    settings=settings,
                    skip_vlm=False,
                    input_mode="requirement",
                )
                total += 1
                if art.render_status == "success":
                    ok += 1
                print(
                    f"[{total}] scenario {dtype} id={art.id} render={art.render_status}",
                    flush=True,
                )
        for code in SOURCE_SNIPPETS:
            for dtype in TYPES:
                art = run_single_generation(
                    session,
                    requirement=code,
                    diagram_type=dtype,
                    project_id=project.id,
                    settings=settings,
                    skip_vlm=False,
                    input_mode="source_code",
                )
                total += 1
                if art.render_status == "success":
                    ok += 1
                print(
                    f"[{total}] source_code {dtype} id={art.id} render={art.render_status}",
                    flush=True,
                )
        count = len(session.exec(select(UMLArtifact)).all())
    print(f"DONE run={total} render_ok={ok} db_total={count}", flush=True)


if __name__ == "__main__":
    main()
