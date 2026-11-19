"""Import grouped EEAI warehouse extracts into the shared snapshot format."""
import csv
import hashlib
import io
from pathlib import Path

from . import config, survey
from dashboard import human_forecasts


def ingest(directory, extracted_on):
    root = Path(directory)
    question_set = survey.load()
    questions = {q["id"]: q for q in question_set["questions"]}
    aliases = {"whitecollar": "jobs_business_analytical", "bluecollar": "jobs_skilled_trade_industrial",
               "pinkcollar": "jobs_care_service"}
    records = []
    expected = {(q["id"], h["id"], s, str(p)) for q in questions.values() for h in q["horizons"]
                if not h["added"] for s in ("unconditional", "slow", "moderate", "rapid")
                for p in ([10, 50, 90] if q["uncertainty"] and s in ("rapid", "unconditional") else [50])}
    progress = {"ai_progress_scenario": "scenario_probabilities", "physical_systems": "household_robot",
                "reliability": "reliability"}
    for kind in ("economic", "probabilities"):
        source = root / (kind + ".csv")
        data = source.read_bytes()
        snapshot = hashlib.sha256(data).hexdigest()
        for row in csv.DictReader(io.StringIO(data.decode())):
            target = row["target_variable_id"]
            if kind == "economic":
                q = aliases.get(target, target)
                year, condition, percentile = row["target_year"], row["scenario"], row["percentile"]
                if (q, year, condition, percentile) not in expected:
                    continue
                stat, unit, method = "p" + percentile, questions[q]["unit"], "weighted_median"
                option = ""
            else:
                q, year, condition = progress[target], "2030", "unconditional"
                stat, unit, method = "probability", "%", "weighted_mean"
                option = row["bin_id"]
                options = {"slow", "moderate", "rapid"} if q == "scenario_probabilities" else {"true"}
                if option not in options or not 0 <= float(row[method]) <= 100:
                    raise ValueError(f"Invalid probability for {target} ({option})")
            records.append(dict(project="eeai", instrument=question_set["instrument"], question=q,
                                horizon=year, condition=condition, option=option, elicited_statistic=stat,
                                cohort=row["cohort"], aggregation=method, value=row[method], unit=unit,
                                respondents=row["responses"], survey="final-survey-full", source_target=target,
                                source_extract=source.name, extract_sha256=snapshot))
    cohorts = {"econ", "ai_expert", "general_public", "superforecaster"}
    for cohort in cohorts:
        cells = [r for r in records if r["cohort"] == cohort]
        if len(cells) != len(expected) + 5:
            raise ValueError(f"Incomplete coverage for {cohort}")
        keys = {(r["question"], r["horizon"], r["condition"], r["elicited_statistic"], r["option"]) for r in cells}
        if len(keys) != len(cells):
            raise ValueError(f"Duplicate observations for {cohort}")
        if abs(sum(float(r["value"]) for r in cells if r["question"] == "scenario_probabilities") - 100) > 1e-6:
            raise ValueError(f"Scenario probabilities do not sum to 100 for {cohort}")
    if {r["cohort"] for r in records} != cohorts:
        raise ValueError("Unrecognized cohort")
    return human_forecasts.store(config.RESULTS / "human_forecasts", extracted_on, records)
