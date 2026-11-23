"""Mock competitor Flask server ("Locus") on port 5001 for local monitoring demos."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import date
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, url_for

BASE_DIR = Path(__file__).resolve().parent
STATE_PATH = BASE_DIR / "state.json"

app = Flask(__name__, template_folder=str(BASE_DIR / "templates"))


def read_state() -> dict[str, bool]:
    if not STATE_PATH.exists():
        return {"locus_ai_summary_visible": False}
    data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {"locus_ai_summary_visible": bool(data.get("locus_ai_summary_visible", False))}


def write_state(new_state: dict[str, bool]) -> None:
    fd, tmp_name = tempfile.mkstemp(prefix=".state_", suffix=".tmp", dir=str(STATE_PATH.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(new_state, fh, indent=2)
        os.replace(tmp_path, STATE_PATH)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise


@app.get("/changelog")
def changelog():
    state = read_state()
    return render_template(
        "changelog.html",
        locus_ai_summary_visible=state["locus_ai_summary_visible"],
        last_updated=date.today().strftime("%B %d, %Y"),
    )


@app.get("/pricing")
def pricing():
    state = read_state()
    return render_template(
        "pricing.html",
        locus_ai_summary_visible=state["locus_ai_summary_visible"],
        last_updated=date.today().strftime("%B %d, %Y"),
    )


@app.post("/toggle")
def toggle():
    state = read_state()
    updated = {"locus_ai_summary_visible": not state["locus_ai_summary_visible"]}
    write_state(updated)
    return redirect(url_for("changelog"))


@app.get("/state")
def get_state():
    return jsonify(read_state())


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=False)
