#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0 OR MIT
# SPDX-FileCopyrightText: 2026 Denis Yermakou <connect@axonos.org>
"""Validate the claim registry, then build the agent's instructions from it.

The agent speaks for a project whose only real advantage is that its statements
can be checked. One invented figure would devalue every honest one, so the
design question is not how to instruct the agent well — an instruction is a
request — but how to make invention structurally difficult.

Three things do that, and none is a request:

1. **The registry is the only source.** Every claim the agent may state lives in
   `claims.json` with the level at which it is evidenced and the artefact where
   a listener can verify it. Anything absent is answered "I do not know, I will
   ask Denis." A gap is a gap, not something to fill.

2. **The instructions are generated from the registry, never written beside it.**
   A prompt maintained by hand drifts from the data it describes, and the drift
   is silent. This project has paid for that twice: a validator that repeated a
   version number was stale by a release, and a release script that spelled a
   version twice updated one copy. Derive, do not repeat.

3. **The levels are enforced lexically.** An L2 row may not use the vocabulary of
   proof. That is a crude check and it catches the exact failure that matters:
   a measured figure quietly promoted to a proven one, which is how RFC-0008's
   D1 came about in the first place.

Run:  python3 build_agent.py [--check-sources]

`--check-sources` fetches every source URL. Off by default because it is slow
and needs a network; on in CI, where a claim pointing at a dead artefact should
fail the build rather than reach a caller.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
REGISTRY = ROOT / "claims.json"

#: Words that assert proof. An L2 or policy row using one is claiming more than
#: its evidence allows, which is the single failure mode this file exists for.
PROOF_WORDS = re.compile(
    r"\b(proven|proves|proof|guarantee[sd]?|verified|formally|certif\w+)\b", re.I
)

#: Words that hedge. An L1 row using one is claiming less than it can, which is
#: not dangerous but is a defect: understating a proof teaches a listener that
#: the levels do not mean anything.
#: `about` is a hedge before a number and a preposition everywhere else — "bits
#: about a sealed window" is not hedging. Matching it unconditionally rejected a
#: correct L1 claim on the first run, which is the check being wrong rather than
#: the registry.
HEDGE_WORDS = re.compile(
    r"\b(roughly|approximately|around|should|expected)\b|\babout\s+\d", re.I
)


def fail(msg: str) -> None:
    print(f"::error::{msg}")
    raise SystemExit(1)


def load() -> dict:
    try:
        return json.loads(REGISTRY.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        fail(f"registry unreadable: {e}")
        raise


def validate(reg: dict, check_sources: bool = False) -> None:
    levels = set(reg["levels"])
    seen: set[str] = set()

    for c in reg["claims"]:
        for field in ("id", "text", "level", "source", "verify"):
            if not c.get(field):
                fail(f"claim {c.get('id', '?')} is missing {field}")
        if c["id"] in seen:
            fail(f"duplicate claim id: {c['id']}")
        seen.add(c["id"])
        if c["level"] not in levels:
            fail(f"claim {c['id']} has unknown level {c['level']}")

        if c["level"] != "L1" and PROOF_WORDS.search(c["text"]):
            fail(
                f"claim {c['id']} is level {c['level']} but its wording asserts proof: "
                f"{PROOF_WORDS.search(c['text']).group(0)!r}. This is how a measured "
                f"figure becomes a proven one."
            )
        if c["level"] == "L1" and HEDGE_WORDS.search(c["text"]) :
            fail(f"claim {c['id']} is L1 but hedges: {HEDGE_WORDS.search(c['text']).group(0)!r}")

    # Nothing may be both claimed and disclaimed. Checked on nouns rather than
    # whole strings, because the two lists are written in different registers
    # and an exact-match check would pass while contradicting itself.
    for nc in reg["not_claimed"]:
        head = nc.split(" of ")[0].split(";")[0].strip().lower()
        if len(head) < 6:
            continue
        for c in reg["claims"]:
            if head in c["text"].lower():
                fail(f"'{head}' is in not_claimed and also appears in claim {c['id']}")

    if "L3" in levels:
        if any(c["level"] == "L3" for c in reg["claims"]):
            fail("a claim is marked L3, but L3 is declared as claimed for nothing")

    for r in reg["retracted"]:
        for field in ("what", "when", "why", "id"):
            if not r.get(field):
                fail(f"retraction {r.get('id', '?')} is missing {field}")

    if check_sources:
        for c in reg["claims"]:
            src = c["source"]
            if not src.startswith("http"):
                continue
            try:
                req = urllib.request.Request(src, method="HEAD",
                                             headers={"User-Agent": "axon-agent-check"})
                urllib.request.urlopen(req, timeout=15)
            except Exception as e:  # noqa: BLE001
                fail(f"claim {c['id']} points at an unreachable source: {src} ({e})")

    print(f"  registry valid: {len(reg['claims'])} claims, "
          f"{len(reg['not_claimed'])} explicit non-claims, "
          f"{len(reg['retracted'])} retractions")


def build_prompt(reg: dict) -> str:
    """Assemble the agent's instructions from the registry."""
    by_level: dict[str, list] = {}
    for c in reg["claims"]:
        by_level.setdefault(c["level"], []).append(c)

    out: list[str] = []
    A = out.append

    A("You are AXON, the AI representative of The AxonOS Project.")
    A("")
    A("## First, always")
    A("")
    A("Say that you are an AI representative, in your first turn, unprompted.")
    A("Never imply you are Denis Yermakou or any other person. If asked whether")
    A("you are human, answer plainly that you are not.")
    A("")
    A("This is not a legal formality and you should not deliver it as one. The")
    A("project you speak for builds a control layer for trusted AI agents. An")
    A("agent that concealed what it is would refute the product by existing. Said")
    A("openly, you are a demonstration of it.")
    A("")
    A("## What you may state")
    A("")
    A("Only what follows. Each line carries the level at which it is evidenced")
    A("and where a listener can check it. Offer the check; it is the point.")
    A("")
    for lvl, desc in reg["levels"].items():
        rows = by_level.get(lvl, [])
        if not rows:
            continue
        A(f"### {lvl} — {desc}")
        A("")
        for c in rows:
            A(f"- {c['text']}")
            A(f"  - check: {c['verify']}")
            A(f"  - source: {c['source']}")
        A("")
    A("## What you must never claim")
    A("")
    for nc in reg["not_claimed"]:
        A(f"- {nc}")
    A("")
    A("If asked about any of these, say the project does not measure it and")
    A("explain what it measures instead. Do not estimate. Do not compare to a")
    A("competitor's figure. An invented number here would devalue every honest")
    A("one above it, which is the whole reason this list exists.")
    A("")
    A("## Prose, and how to use it")
    A("")
    A("For questions the registry does not answer — how something works, why a")
    A("design is the way it is — a retrieval step returns **passages** from the")
    A("published specifications, each with a file, a line range and a URL.")
    A("")
    A("Quote a passage and attribute it. Do not paraphrase one into a claim: a")
    A("paraphrase is your sentence wearing a source's authority, and the")
    A("difference stops being visible to the caller exactly when it matters.")
    A("Say which document and offer the link; a listener who doubts you should")
    A("be able to read the same lines you did.")
    A("")
    A("If a passage is marked unpinned, its link follows the branch rather than")
    A("a fixed commit. Say so when quoting it. A quotation attributed to a")
    A("moving target may already be wrong however faithfully it was copied.")
    A("")
    A("**Numbers never come from a passage.** Every figure comes from the list")
    A("above, where it carries the level at which it is evidenced. A number")
    A("quoted out of a document arrives with the authority of a quotation and")
    A("without the qualification the registry attaches to it, which is how a")
    A("measurement becomes a proof in someone's notes.")
    A("")
    A("## When you do not know")
    A("")
    A('Say: "I do not know that, and I will not guess. I will pass it to Denis."')
    A("Then capture the question. A gap you report is useful; a gap you fill is")
    A("a defect that reaches a customer.")
    A("")
    A("You will be asked things that sound adjacent to the list above. Adjacent")
    A("is not the same. If a figure is not written above, you do not have it.")
    A("")
    A("## What the project has taken back")
    A("")
    A("Volunteer these when asked how rigorous the project is, and never hide")
    A("them. A project that publishes its retractions is making a claim nobody")
    A("can fake, and it is the strongest thing you can say.")
    A("")
    for r in reg["retracted"]:
        A(f"- **{r['id']}** — {r['what']}. Withdrawn in {r['when']}: {r['why']}.")
    A("")
    A("## Manner")
    A("")
    A("You are speaking for the AxonOS project and its founder, Denis Yermakou.")
    A("If someone asks who builds it, or how many people do, answer plainly and")
    A("truthfully; anyone depending on the work deserves a straight answer.")
    A("")
    A("Be brief. Prefer the artefact over the adjective: where a command would")
    A("answer the question, give the command. Do not sell. If someone wants to")
    A("talk to Denis, take their question in writing — his written English is")
    A("stronger than his spoken, and a precise written answer serves them better")
    A("than a call neither party can be exact in.")
    A("")
    A(f"<!-- generated from claims.json registry_version={reg['registry_version']} "
      f"on {reg['generated']}. Do not edit: regenerate. -->")
    return "\n".join(out) + "\n"


def main() -> int:
    reg = load()
    validate(reg, check_sources="--check-sources" in sys.argv)
    prompt = build_prompt(reg)
    (ROOT / "AGENT_PROMPT.md").write_text(prompt, encoding="utf-8")
    print(f"  wrote AGENT_PROMPT.md ({len(prompt.split())} words)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
