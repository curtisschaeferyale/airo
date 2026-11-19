"""Replays using published releases, with no network or installation credentials."""
import json
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from eeai import baselines, build, config, decisions, export, resolve, survey
from dashboard import resolutions


class ResolutionTest(unittest.TestCase):
    def setUp(self):
        self.doc = survey.load()
        self.q = {q["id"]: q for q in self.doc["questions"]}
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        override = patch.object(config, "RESULTS", self.root)
        override.start()
        self.addCleanup(override.stop)

    def test_published_releases_through_page_and_download(self):
        # BLS 2024-02-02 Employment Situation; BEA September 2024 annual update
        # and 2025-01-30 GDP advance release. Annual rates are in percent.
        examples = [
            ("unemployment", "2024", "2024-02-02", [3.7], 3.7),
            ("gdp", "2025", "2025-01-30", [-2.2, 6.1, 2.5, 2.9, 2.8], 2.39),
        ]
        db = self.root / "resolutions.sqlite"
        for qid, year, vintage, values, expected in examples:
            q = self.q[qid]
            periods = resolve.dates(q["resolution"]["method"], int(year))
            rows = [dict(date=p, value=str(v), realtime_start=vintage, realtime_end="9999-12-31")
                    for p, v in zip(periods, values, strict=True)]
            self.assertIsNone(resolve.outcome_for(q, periods, {q["resolution"]["series"]: rows}, vintage[:8] + "01"))
            outcome = resolve.outcome_for(q, periods, {q["resolution"]["series"]: rows}, vintage)
            self.assertEqual(round(outcome["value"], 2), expected)
            self.assertEqual(dict(survey.history(config.HISTORY)[qid])[year + "-01-01"], expected)
            resolutions.record(db, qid, year, q["resolution"], outcome)
            q["horizons"] = [{"id": year, "text": year}]
        records = resolutions.snapshot(db)
        blob = build.build(self.doc, runs=[], outcomes=records)
        self.assertIn('"vintage": "2025-01-30"', build.page(blob))
        path = self.root / "out.zip"
        export.bundle(path, self.doc, [], outcomes=records)
        with zipfile.ZipFile(path) as archive:
            data = json.loads(archive.read("resolutions.json"))
        for row in data:
            q = next(q for q in blob["questions"] if q["id"] == row["question"])
            self.assertEqual(q["horizons"][0]["actual"]["inputs"], row["inputs"])

    def test_job_shares_reproduce_survey_examples(self):
        counts = {"USINFO": 2963, "USFIRE": 9165, "USPBS": 22668, "USGOOD": 21631,
                  "USTPU": 28799, "USEHS": 26033, "USLAH": 16716, "USSERV": 5917, "CLF16OV": 167308}
        for qid, expected in [("jobs_business_analytical", 20.8), ("jobs_skilled_trade_industrial", 12.9),
                              ("jobs_care_service", 46.3)]:
            rule = self.q[qid]["resolution"]
            values = {key: {"2024-01-01": counts[key]} for key in resolve.source_ids(rule)}
            self.assertEqual(round(resolve.calculate(rule, values, ["2024-01-01"]), 1), expected)

    def test_productivity_income_and_labor_share_units(self):
        periods = resolve.dates("q4_five_year_growth", 2030)
        self.assertEqual(periods, [f"{y}-10-01" for y in range(2025, 2030)])
        income = self.q["median_household_income"]["resolution"]
        inputs = {income["series"]: {"2023-01-01": 84730, "2025-01-01": 87460},
                  income["nominal"]: {"2023-01-01": 80610}}
        self.assertEqual(resolve.calculate(income, inputs, ["2023-01-01"]), 80610)
        self.assertAlmostEqual(resolve.calculate(income, inputs, ["2025-01-01"]), 87460 * 80610 / 84730)
        share = self.q["labor_share"]["resolution"]
        value = resolve.calculate(share, {share["series"]: {"2023-01-01": 96.618}}, ["2023-01-01"])
        self.assertAlmostEqual(value, dict(survey.history(config.HISTORY)["labor_share"])["2023-01-01"])

    def test_failed_baseline_refresh_preserves_prior_snapshot(self):
        day = date(2026, 11, 19)
        rows = lambda values: [dict(date=k, value=str(v), realtime_start=str(day), realtime_end=str(day))
                               for k, v in values.items()]
        def reader(key, periods, as_of, latest=False):
            self.assertTrue(latest)
            return rows({"2025-01-01": 4, "2026-01-01": 4.3})
        with patch.object(survey, "load", return_value={"questions": [self.q["unemployment"]]}):
            baselines.refresh(day, reader)
            source = baselines.current(day)
            before = source.read_bytes()
            self.assertEqual(survey.history(source)["unemployment"][-1], ("2026-01-01", 4.3))
            with self.assertRaises(ValueError):
                baselines.refresh(day, lambda *args, **kwargs: [])
            self.assertEqual(source.read_bytes(), before)

    def test_adjudication_and_correction(self):
        decision = dict(question="ai_electricity", horizon="2030", version=1, value=2.0,
                        source="Example study table 2", rationale="Reviewed nationwide estimate",
                        reviewer="Example reviewer", period="2030", vintage="2031-05-01")
        path = self.root / "decision.json"
        path.write_text(json.dumps(decision))
        with self.assertRaises(ValueError):
            decisions.apply(path, date(2030, 11, 1))
        today = date(2031, 6, 1)
        decisions.apply(path, today)
        db = self.root / "resolutions.sqlite"
        key = ("ai_electricity", "2030", 1)
        previous = resolutions.snapshot(db)[key]
        path.write_text(json.dumps(dict(decision, previous=previous, value=2.1, correction_reason="Erratum")))
        decisions.apply(path, today)
        self.assertEqual(resolutions.snapshot(db)[key]["supersedes"], previous)
        with self.assertRaises(ValueError):
            decisions.apply(path, today)
