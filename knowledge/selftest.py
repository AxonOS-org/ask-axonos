#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0 OR MIT
# SPDX-FileCopyrightText: 2026 Denis Yermakou <connect@axonos.org>
"""Feed the validator the defects it exists to catch.

A check nobody has watched fail is a check nobody should trust. Each case here
is a real failure this project shipped, reduced to its smallest form.
"""
import copy, json, pathlib, subprocess, sys, tempfile

BASE = json.loads(pathlib.Path("claims.json").read_text(encoding="utf-8"))
ok = True

def run(reg, label, must_fail=True):
    global ok
    d = pathlib.Path(tempfile.mkdtemp())
    (d / "claims.json").write_text(json.dumps(reg), encoding="utf-8")
    (d / "build_agent.py").write_text(pathlib.Path("build_agent.py").read_text(), encoding="utf-8")
    r = subprocess.run([sys.executable, "build_agent.py"], cwd=d, capture_output=True, text=True)
    failed = r.returncode != 0
    good = failed == must_fail
    ok &= good
    note = (r.stdout + r.stderr).strip().splitlines()
    print(f"  {'✓' if good else '✗'} {label:<52} {'refused' if failed else 'accepted'}")
    if failed and must_fail and note:
        print(f"       {note[0][:96]}")

# D1: a measured figure promoted to a proven one. This is how the seven-stage
# WCET table came to be presented as measurement.
r = copy.deepcopy(BASE)
next(c for c in r["claims"] if c["id"] == "wcrt_observed")["text"] = \
    "972 microseconds proven worst-case response on STM32F407"
run(r, "L2 claim worded as proof (the D1 shape)")

# A claim that contradicts the explicit non-claims.
r = copy.deepcopy(BASE)
r["claims"].append({"id":"acc","text":"classification accuracy of 82.4 per cent on four classes",
                    "level":"L2","source":"x","verify":"y"})
run(r, "a figure that not_claimed forbids")

# A source that no longer exists — the artefact behind a claim must resolve.
r = copy.deepcopy(BASE)
next(c for c in r["claims"] if c["id"] == "proofs")["source"] = ""
run(r, "claim with no source")

# L3 is declared as claimed for nothing; a row claiming it contradicts the page.
r = copy.deepcopy(BASE)
next(c for c in r["claims"] if c["id"] == "langs")["level"] = "L3"
run(r, "a claim marked L3 while L3 is disclaimed")

# Two rows with one id: the second silently shadows the first in any lookup.
r = copy.deepcopy(BASE)
r["claims"].append(copy.deepcopy(r["claims"][0]))
run(r, "duplicate claim id")

# A retraction missing its reason is a retraction nobody can learn from.
r = copy.deepcopy(BASE)
r["retracted"][0]["why"] = ""
run(r, "retraction with no reason")

# And the registry as it stands must pass.
run(copy.deepcopy(BASE), "the registry as written", must_fail=False)

print()
print("ИТОГ:", "все проверки ведут себя как задумано" if ok else "ЕСТЬ ПРОБЛЕМА")
raise SystemExit(0 if ok else 1)
