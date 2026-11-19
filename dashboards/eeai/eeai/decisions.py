"""Record a sourced human decision or a reviewed correction from a JSON file."""
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path

from . import config, survey
from dashboard import resolutions


def apply(path, today=None):
    decision = json.loads(Path(path).read_text())
    today = today or datetime.now(timezone.utc).date()
    doc = survey.load()
    qid, horizon = decision["question"], decision["horizon"]
    year = int(horizon)
    value = decision["value"]
    if qid == "ai_scenario":
        rule = doc["scenarios"]["resolution"]
        if horizon != "2030" or value not in [s["id"] for s in doc["scenarios"]["items"]]:
            raise ValueError("Expected a 2030 survey scenario")
        unit = "scenario"
    else:
        q = next((q for q in doc["questions"] if q["id"] == qid), None)
        if not q or horizon not in [h["id"] for h in q["horizons"]]:
            raise ValueError("Unknown question or horizon")
        rule, unit = q["resolution"], q["unit"]
        if rule["method"] != "adjudicated" and "previous" not in decision:
            raise ValueError("This question resolves automatically")
        if type(value) not in (int, float) or not math.isfinite(value) or not q["bounds"][0] <= value <= q["bounds"][1]:
            raise ValueError("Invalid outcome value")
    vintage = date.fromisoformat(decision["vintage"])
    earliest = date(year + 1, 1, 1) if qid in ("ai_scenario", "ai_electricity", "life_satisfaction", "wealth_inequality", "median_household_income") else date(year, 1, 1)
    if not earliest <= vintage <= today or decision["version"] != rule["version"]:
        raise ValueError("Invalid evidence date or resolution rule version")
    fields = ("source", "rationale", "reviewer", "period")
    if not all(isinstance(decision.get(f), str) and decision[f].strip() for f in fields):
        raise ValueError("Decision requires source, rationale, reviewer and measurement period")
    outcome = {k: decision[k] for k in (*fields, "value", "vintage")}
    outcome["unit"] = unit
    db = config.RESULTS / "resolutions.sqlite"
    if "previous" in decision:
        resolutions.correct(db, qid, horizon, rule, outcome, previous=decision["previous"],
                            reason=decision["correction_reason"])
    else:
        resolutions.record(db, qid, horizon, rule, outcome)
