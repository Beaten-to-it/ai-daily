import argparse
import json
import re
from pathlib import Path

from . import codex_cli
from . import ledger as ledger_mod
from .config import run_dir
from .models import (
    candidate_id,
    canonicalize_url,
    materialize_selected,
    validate_decision_coverage,
    validate_decisions,
    validate_selection,
)


ROOT = Path(__file__).resolve().parent.parent
PROMPT = ROOT / "prompts" / "select.md"
SELECTION_SCHEMA = ROOT / "schemas" / "selection.schema.json"
_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def build_prompt_input(candidates, digest, date):
    payload = {"date": date, "recent_ledger": digest, "candidates": candidates}
    return PROMPT.read_text(encoding="utf-8").replace(
        "<<INPUT>>", json.dumps(payload, ensure_ascii=False, indent=2)
    ).replace("<DATE>", date)


def parse_selection(raw):
    """Compatibility parser for archived model responses and fixtures."""
    match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.S)
    blob = match.group(1) if match else raw[raw.find("{"):raw.rfind("}") + 1]
    return json.loads(blob)


def run_codex(text, date, timeout=300):
    return codex_cli.run_json(
        text,
        SELECTION_SCHEMA,
        run_dir(date) / "codex-work" / "selection",
        timeout,
    )


def normalize_candidate(candidate):
    normalized = dict(candidate)
    normalized["canonical_url"] = canonicalize_url(normalized.get("url", ""))
    expected_id = candidate_id(normalized.get("url", ""))
    supplied_id = normalized.get("candidate_id")
    if supplied_id and supplied_id != expected_id:
        raise ValueError(f"candidate_id mismatch: {supplied_id}")
    normalized["candidate_id"] = expected_id
    normalized.setdefault("lane", "official")
    normalized.setdefault("discovered_via", "")
    return normalized


def collapse_identical_decisions(model):
    if not isinstance(model, dict) or not isinstance(model.get("decisions"), list):
        return model
    seen = set()
    decisions = []
    for row in model["decisions"]:
        key = json.dumps(row, ensure_ascii=False, sort_keys=True)
        if key not in seen:
            seen.add(key)
            decisions.append(row)
    return {**model, "decisions": decisions}


def materialize_selection(model, candidates, date):
    decisions_by_id = {row["candidate_id"]: row for row in model["decisions"]}
    ordered_decisions = [decisions_by_id[candidate["candidate_id"]] for candidate in candidates]
    items = [materialize_selected(candidate, decisions_by_id[candidate["candidate_id"]])
             for candidate in candidates
             if decisions_by_id[candidate["candidate_id"]]["decision"] == "select"]
    items.sort(key=lambda item: item["rank"])
    return {
        "date": date,
        "decisions": ordered_decisions,
        "items": items,
        "selected_count": len(items),
        "skipped_count": len(ordered_decisions) - len(items),
        "generated_with": model["generated_with"],
    }


def select(date):
    directory = run_dir(date)
    candidates = [normalize_candidate(candidate) for candidate in json.loads(
        (directory / "candidates.json").read_text(encoding="utf-8")
    )]
    if not candidates:
        result = {
            "date": date,
            "decisions": [],
            "items": [],
            "selected_count": 0,
            "skipped_count": 0,
            "generated_with": "local-empty",
        }
        (directory / "selection.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return result

    digest = ledger_mod.ledger_digest(ledger_mod.read_recent(days=14, today=date))
    model = collapse_identical_decisions(
        run_codex(build_prompt_input(candidates, digest, date), date)
    )
    errors = validate_decisions(model)
    if model.get("date") != date:
        errors.append(f"date mismatch: {model.get('date')} != {date}")
    errors.extend(validate_decision_coverage(model, candidates))
    if errors:
        raise ValueError("selection decisions invalid: " + "; ".join(errors[:12]))

    result = materialize_selection(model, candidates, date)
    errors = validate_selection(result)
    if errors:
        raise ValueError("selection materialization invalid: " + "; ".join(errors[:12]))
    (directory / "selection.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    args = parser.parse_args(argv)
    if not _DATE_RE.fullmatch(args.date or ""):
        parser.error("--date must be YYYY-MM-DD")
    result = select(args.date)
    print(f"selected {result['selected_count']} (skipped {result['skipped_count']}) "
          f"-> runs/{args.date}/selection.json")


if __name__ == "__main__":
    main()
