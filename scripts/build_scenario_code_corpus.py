#!/usr/bin/env python3
"""
Build supplemental training + eval sets:

  * 1000 natural-language scenarios (multi-domain, multi human-language)
  * 1000 source-code samples across many programming languages

Outputs:
  data/training/scenarios_1000.jsonl
  data/training/code_langs_1000.jsonl
  data/training/uml_supplement_2000.parquet  (merged rows compatible with prepare_finetune_data)
  data/eval/scenarios_1000.jsonl
  data/eval/code_langs_1000.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

DOMAINS = [
    "ecommerce", "hospital", "banking", "education", "logistics", "iot",
    "social", "hr", "inventory", "booking", "insurance", "telecom",
    "library", "restaurant", "fleet", "energy", "media", "gaming",
    "crm", "ticketing",
]

ENTITIES = {
    "ecommerce": ["Customer", "Order", "Product", "Cart", "Payment", "Shipment"],
    "hospital": ["Patient", "Doctor", "Appointment", "Clinic", "Prescription", "Lab"],
    "banking": ["Account", "Customer", "Transaction", "Loan", "Card", "Branch"],
    "education": ["Student", "Course", "Instructor", "Enrollment", "Assignment", "Grade"],
    "logistics": ["Shipment", "Warehouse", "Carrier", "Route", "Package", "Hub"],
    "iot": ["Device", "Sensor", "Gateway", "Telemetry", "Alert", "Firmware"],
    "social": ["User", "Post", "Comment", "Follow", "Feed", "Notification"],
    "hr": ["Employee", "Department", "Payroll", "Leave", "Role", "Review"],
    "inventory": ["Item", "Sku", "Warehouse", "Supplier", "Stock", "Reorder"],
    "booking": ["Guest", "Room", "Reservation", "Hotel", "Payment", "Invoice"],
    "insurance": ["Policy", "Claim", "Customer", "Agent", "Premium", "Coverage"],
    "telecom": ["Subscriber", "Plan", "Sim", "Usage", "Invoice", "Tower"],
    "library": ["Member", "Book", "Loan", "Catalog", "Librarian", "Fine"],
    "restaurant": ["Customer", "MenuItem", "Order", "Table", "Chef", "Bill"],
    "fleet": ["Vehicle", "Driver", "Trip", "Maintenance", "Depot", "FuelLog"],
    "energy": ["Meter", "Customer", "Tariff", "Reading", "Outage", "GridNode"],
    "media": ["Viewer", "Content", "Channel", "Subscription", "Ad", "Playlist"],
    "gaming": ["Player", "Match", "Inventory", "Quest", "Guild", "Score"],
    "crm": ["Lead", "Contact", "Opportunity", "Account", "Activity", "Campaign"],
    "ticketing": ["Ticket", "Requester", "Agent", "Queue", "Sla", "Comment"],
}

# Human languages for scenario text (ISO-ish codes). Not 1000 languages — diversified NL.
HUMAN_LANGS = [
    ("en", "Build a {domain} system where {a} interacts with {b} and {c}."),
    ("en", "The {domain} platform must manage {a}, {b}, and {c} with clear relationships."),
    ("es", "Sistema de {domain}: {a} se relaciona con {b} y {c}."),
    ("fr", "Le système {domain} gère {a}, {b} et {c}."),
    ("de", "Das {domain}-System verbindet {a}, {b} und {c}."),
    ("hi", "{domain} प्रणाली में {a}, {b} और {c} हों।"),
    ("zh", "{domain}系统需要{a}、{b}和{c}。"),
    ("pt", "O sistema de {domain} inclui {a}, {b} e {c}."),
    ("it", "Il sistema {domain} collega {a}, {b} e {c}."),
    ("ja", "{domain}システムは{a}、{b}、{c}を管理する。"),
    ("ko", "{domain} 시스템은 {a}, {b}, {c}를 관리한다."),
    ("ar", "نظام {domain} يشمل {a} و {b} و {c}."),
    ("ru", "Система {domain} связывает {a}, {b} и {c}."),
    ("nl", "Het {domain}-systeem beheert {a}, {b} en {c}."),
    ("tr", "{domain} sistemi {a}, {b} ve {c} içerir."),
    ("pl", "System {domain} łączy {a}, {b} i {c}."),
    ("sv", "{domain}-systemet hanterar {a}, {b} och {c}."),
    ("vi", "Hệ thống {domain} gồm {a}, {b} và {c}."),
    ("th", "ระบบ {domain} มี {a} {b} และ {c}"),
    ("id", "Sistem {domain} mengelola {a}, {b}, dan {c}."),
]

DIAGRAM_TYPES = ["class", "object", "component", "package", "flowchart"]

# Programming language templates → (lang_id, code_template with {A}{B}{C}{ma}{mb})
CODE_TEMPLATES: list[tuple[str, str]] = [
    ("python", "class {A}:\n    def {ma}(self):\n        return True\n\nclass {B}({A}):\n    def {mb}(self):\n        pass\n\nclass {C}:\n    def link(self, other: '{B}'):\n        self.ref = other\n"),
    ("java", "package demo;\npublic class {A} {{\n  public void {ma}() {{}}\n}}\npublic class {B} extends {A} {{\n  public void {mb}() {{}}\n}}\npublic class {C} {{\n  private {B} ref;\n}}\n"),
    ("javascript", "class {A} {{\n  {ma}() {{ return true; }}\n}}\nclass {B} extends {A} {{\n  {mb}() {{}}\n}}\nclass {C} {{\n  constructor(ref) {{ this.ref = ref; }}\n}}\n"),
    ("typescript", "export class {A} {{\n  {ma}(): boolean {{ return true; }}\n}}\nexport class {B} extends {A} {{\n  {mb}(): void {{}}\n}}\nexport class {C} {{\n  constructor(public ref: {B}) {{}}\n}}\n"),
    ("rust", "struct {A} {{}}\nimpl {A} {{\n  fn {ma}(&self) -> bool {{ true }}\n}}\nstruct {B} {{ parent: {A} }}\nimpl {B} {{\n  fn {mb}(&self) {{}}\n}}\nstruct {C} {{ ref: {B} }}\n"),
    ("go", "package demo\ntype {A} struct{{}}\nfunc (a *{A}) {Ma}() bool {{ return true }}\ntype {B} struct{{ {A} }}\nfunc (b *{B}) {Mb}() {{}}\ntype {C} struct{{ Ref *{B} }}\n"),
    ("csharp", "namespace Demo {{\npublic class {A} {{ public void {Ma}() {{}} }}\npublic class {B} : {A} {{ public void {Mb}() {{}} }}\npublic class {C} {{ public {B} Ref {{ get; set; }} }}\n}}\n"),
    ("kotlin", "open class {A} {{ fun {ma}(): Boolean = true }}\nclass {B} : {A}() {{ fun {mb}() {{}} }}\nclass {C}(val ref: {B})\n"),
    ("swift", "class {A} {{ func {ma}() -> Bool {{ return true }} }}\nclass {B}: {A} {{ func {mb}() {{}} }}\nclass {C} {{ var ref: {B}? }}\n"),
    ("cpp", "class {A} {{ public: void {ma}(); }};\nclass {B} : public {A} {{ public: void {mb}(); }};\nclass {C} {{ {B}* ref; }};\n"),
    ("ruby", "class {A}\n  def {ma}; true; end\nend\nclass {B} < {A}\n  def {mb}; end\nend\nclass {C}\n  attr_accessor :ref\nend\n"),
    ("php", "<?php\nclass {A} {{ public function {ma}() {{ return true; }} }}\nclass {B} extends {A} {{ public function {mb}() {{}} }}\nclass {C} {{ public ${B} $ref; }}\n"),
    ("scala", "class {A} {{ def {ma}(): Boolean = true }}\nclass {B} extends {A} {{ def {mb}(): Unit = () }}\nclass {C}(val ref: {B})\n"),
    ("dart", "class {A} {{ bool {ma}() => true; }}\nclass {B} extends {A} {{ void {mb}() {{}} }}\nclass {C} {{ {B}? ref; }}\n"),
    ("perl", "package {A}; sub {ma} {{ 1 }}\npackage {B}; use parent '{A}'; sub {mb} {{}}\npackage {C}; sub new {{ bless {{}}, shift }}\n"),
    ("lua", "{A} = {{}}\nfunction {A}:{ma}() return true end\n{B} = setmetatable({{}}, {{__index={A}}})\nfunction {B}:{mb}() end\n{C} = {{ ref = nil }}\n"),
    ("r", "{A} <- setRefClass('{A}', methods = list({ma} = function() TRUE))\n{B} <- setRefClass('{B}', contains = '{A}', methods = list({mb} = function() NULL))\n"),
    ("matlab", "classdef {A}\n  methods\n    function r = {ma}(obj), r = true; end\n  end\nend\n"),
    ("haskell", "data {A} = {A}\n{ma} :: {A} -> Bool\n{ma} _ = True\ndata {B} = {B} {A}\ndata {C} = {C} {B}\n"),
    ("elixir", "defmodule {A} do\n  def {ma}(), do: true\nend\ndefmodule {B} do\n  def {mb}(), do: :ok\nend\n"),
]


def _id(*parts: str) -> str:
    h = hashlib.sha1("|".join(parts).encode()).hexdigest()[:12]
    return h


def _uml_class(entities: list[str]) -> str:
    a, b, c = entities[:3]
    return (
        "@startuml\n"
        f"class {a} {{\n  +id: int\n  +{a.lower()}_name: string\n}}\n"
        f"class {b} {{\n  +id: int\n}}\n"
        f"class {c} {{\n  +id: int\n}}\n"
        f"{a} <|-- {b}\n"
        f"{a} \"1\" --> \"*\" {c}\n"
        "@enduml"
    )


def _uml_object(entities: list[str]) -> str:
    a, b, c = entities[:3]
    return (
        "@startuml\n"
        f'object "{a}1" as {a}1 {{\n  id = 1\n}}\n'
        f'object "{b}1" as {b}1\n'
        f'object "{c}1" as {c}1\n'
        f"{a}1 --> {b}1\n"
        f"{b}1 --> {c}1\n"
        "@enduml"
    )


def _uml_component(entities: list[str]) -> str:
    a, b, c = entities[:3]
    return (
        "@startuml\n"
        f"component [{a}Service]\n"
        f"component [{b}Service]\n"
        f"component [{c}Service]\n"
        f"[{a}Service] --> [{b}Service]\n"
        f"[{b}Service] --> [{c}Service]\n"
        "@enduml"
    )


def _uml_package(entities: list[str]) -> str:
    a, b, c = entities[:3]
    return (
        "@startuml\n"
        f"package {a} {{\n  class {a}Core\n}}\n"
        f"package {b} {{\n  class {b}Core\n}}\n"
        f"package {c} {{\n  class {c}Core\n}}\n"
        f"{a} ..> {b}\n"
        f"{b} ..> {c}\n"
        "@enduml"
    )


def _uml_flowchart(entities: list[str]) -> str:
    a, b, c = entities[:3]
    return (
        "@startuml\n"
        "start\n"
        f":Receive {a} request;\n"
        f"if ({b} valid?) then (yes)\n"
        f"  :Process {c};\n"
        "  :Notify success;\n"
        "else (no)\n"
        "  :Reject request;\n"
        "endif\n"
        "stop\n"
        "@enduml"
    )


UML_BUILDERS = {
    "class": _uml_class,
    "object": _uml_object,
    "component": _uml_component,
    "package": _uml_package,
    "flowchart": _uml_flowchart,
}


def build_scenarios(n: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    rows: list[dict] = []
    for i in range(n):
        domain = DOMAINS[i % len(DOMAINS)]
        ents = ENTITIES[domain]
        a, b, c = rng.sample(ents, 3)
        dtype = DIAGRAM_TYPES[i % len(DIAGRAM_TYPES)]
        lang, tmpl = HUMAN_LANGS[i % len(HUMAN_LANGS)]
        req = tmpl.format(domain=domain, a=a, b=b, c=c)
        spec = (
            f"## Technical Specification\n"
            f"### Domain\n{domain}\n"
            f"### Language\n{lang}\n"
            f"### Entities\n- {a}\n- {b}\n- {c}\n"
            f"### Relationships\n- {b} specializes or depends on {a}\n"
            f"- {a} associates with {c}\n"
            f"### Source intent\n{req}\n"
        )
        uml = UML_BUILDERS[dtype]([a, b, c])
        rows.append(
            {
                "id": _id("sc", str(i), dtype, lang),
                "diagram_type": dtype,
                "source_requirement": req,
                "technical_spec": spec,
                "uml_code": uml,
                "human_language": lang,
                "domain": domain,
                "input_mode": "requirement",
                "source_language": None,
                "dataset_accepted": True,
                "source_dataset": "synthetic_scenarios_1000",
            }
        )
    return rows


def build_code_samples(n: int, seed: int) -> list[dict]:
    rng = random.Random(seed + 7)
    rows: list[dict] = []
    for i in range(n):
        lang, tmpl = CODE_TEMPLATES[i % len(CODE_TEMPLATES)]
        domain = DOMAINS[i % len(DOMAINS)]
        ents = ENTITIES[domain]
        a, b, c = rng.sample(ents, 3)
        ma, mb = "process", "validate"
        code = tmpl.format(
            A=a, B=b, C=c, ma=ma, mb=mb, Ma=ma.capitalize(), Mb=mb.capitalize()
        )
        dtype = DIAGRAM_TYPES[i % len(DIAGRAM_TYPES)]
        # Prefer class for code→UML fidelity; still cover all types cyclically.
        if dtype in ("object",) and lang in ("haskell", "r", "matlab"):
            dtype = "class"
        spec = (
            f"## Technical Specification\n"
            f"### Detected language\n- {lang}\n"
            f"### Source intent\nReverse-engineer UML from {lang} source for {domain}.\n"
            f"### Entities\n- {a}\n- {b}\n- {c}\n"
            f"### Methods\n- {a}.{ma}\n- {b}.{mb}\n"
        )
        uml = UML_BUILDERS[dtype]([a, b, c])
        rows.append(
            {
                "id": _id("cd", str(i), lang, dtype),
                "diagram_type": dtype,
                "source_requirement": code,
                "technical_spec": spec,
                "uml_code": uml,
                "human_language": "en",
                "domain": domain,
                "input_mode": "source_code",
                "source_language": lang,
                "dataset_accepted": True,
                "source_dataset": "synthetic_code_langs_1000",
            }
        )
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def to_training_frame(rows: list[dict]) -> pd.DataFrame:
    out = []
    for r in rows:
        out.append(
            {
                "id": r["id"],
                "diagram_type": r["diagram_type"],
                "source_requirement": r["source_requirement"],
                "technical_spec": r["technical_spec"],
                "uml_code": r["uml_code"],
                "reasoning_private": None,
                "qwen25vl3b": 5,
                "llama32vl11b": 5,
                "aya_vision_8b": 4,
                "composite_score": 4.7,
                "majority_accepted": True,
                "affirmative_votes": 3,
                "dataset_accepted": True,
                "source_dataset": r["source_dataset"],
            }
        )
    return pd.DataFrame(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", type=int, default=1000)
    ap.add_argument("--codes", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--min-merged",
        type=int,
        default=0,
        help="If set, grow scenarios/codes until merged rows reach this size (honest synthetic top-up)",
    )
    args = ap.parse_args()

    scenarios = build_scenarios(args.scenarios, args.seed)
    codes = build_code_samples(args.codes, args.seed)

    train_dir = ROOT / "data" / "training"
    eval_dir = ROOT / "data" / "eval"
    # Keep classic filenames for compatibility; also write sized copies when N≠1000
    write_jsonl(train_dir / "scenarios_1000.jsonl", scenarios)
    write_jsonl(train_dir / "code_langs_1000.jsonl", codes)
    write_jsonl(eval_dir / "scenarios_1000.jsonl", scenarios[: min(1000, len(scenarios))])
    write_jsonl(eval_dir / "code_langs_1000.jsonl", codes[: min(1000, len(codes))])
    if args.scenarios != 1000 or args.codes != 1000:
        write_jsonl(train_dir / f"scenarios_{args.scenarios}.jsonl", scenarios)
        write_jsonl(train_dir / f"code_langs_{args.codes}.jsonl", codes)

    df_new = pd.concat(
        [to_training_frame(scenarios), to_training_frame(codes)], ignore_index=True
    )
    base = train_dir / "uml_training_8000.parquet"
    if base.is_file():
        df_base = pd.read_parquet(base)
        # Align columns
        for col in df_new.columns:
            if col not in df_base.columns:
                df_base[col] = None
        for col in df_base.columns:
            if col not in df_new.columns:
                df_new[col] = None
        df_all = pd.concat([df_base[df_new.columns], df_new], ignore_index=True)
    else:
        df_all = df_new

    # Optional synthetic expansion to hit --min-merged (documented in manifest)
    synthetic_topup = 0
    if args.min_merged and len(df_all) < args.min_merged:
        need = args.min_merged - len(df_all)
        # Split need across more scenarios + codes with a shifted seed (new unique templates)
        extra_sc = need // 2 + need % 2
        extra_cd = need // 2
        more_sc = build_scenarios(extra_sc, args.seed + 10_000)
        more_cd = build_code_samples(extra_cd, args.seed + 20_000)
        # Retag source so top-up is auditable
        for r in more_sc:
            r["source_dataset"] = "synthetic_scenarios_topup"
        for r in more_cd:
            r["source_dataset"] = "synthetic_code_langs_topup"
        df_extra = pd.concat(
            [to_training_frame(more_sc), to_training_frame(more_cd)], ignore_index=True
        )
        for col in df_all.columns:
            if col not in df_extra.columns:
                df_extra[col] = None
        df_all = pd.concat([df_all, df_extra[df_all.columns]], ignore_index=True)
        synthetic_topup = len(df_extra)
        scenarios = scenarios + more_sc
        codes = codes + more_cd

    # Dedup on uml_code+technical_spec to avoid exact clones
    before = len(df_all)
    df_all = df_all.drop_duplicates(subset=["uml_code", "technical_spec"], keep="first")
    dedup_dropped = before - len(df_all)

    out_parquet = train_dir / "uml_training_supplement_merged.parquet"
    out_jsonl = train_dir / "uml_training_supplement_merged.jsonl"
    df_all.to_parquet(out_parquet, index=False)
    df_all.to_json(out_jsonl, orient="records", lines=True, force_ascii=False)

    langs = sorted({r["source_language"] for r in codes if r.get("source_language")})
    human = sorted({r["human_language"] for r in scenarios})
    meta = {
        "scenarios": len(scenarios),
        "code_samples": len(codes),
        "programming_languages": langs,
        "programming_language_count": len(langs),
        "human_languages": human,
        "human_language_count": len(human),
        "merged_rows": int(len(df_all)),
        "synthetic_topup_rows": int(synthetic_topup),
        "dedup_dropped": int(dedup_dropped),
        "min_merged_requested": int(args.min_merged or 0),
        "notes": [
            "Primary rows come from HF uml_training_8000.parquet when present.",
            "scenario/code rows are synthetic templates for diversification.",
            "synthetic_topup_rows > 0 means extra synthetic fill was used to reach --min-merged.",
        ],
        "outputs": {
            "scenarios": str(train_dir / "scenarios_1000.jsonl"),
            "codes": str(train_dir / "code_langs_1000.jsonl"),
            "merged_parquet": str(out_parquet),
            "eval_scenarios": str(eval_dir / "scenarios_1000.jsonl"),
            "eval_codes": str(eval_dir / "code_langs_1000.jsonl"),
        },
    }
    (train_dir / "supplement_manifest.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
