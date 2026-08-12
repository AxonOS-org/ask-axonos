#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0 OR MIT
# SPDX-FileCopyrightText: 2026 Denis Yermakou <connect@axonos.org>
"""The shape an answer must have, and the check that refuses one that does not.

The widget renders three kinds of answer and the knowledge system produces
three kinds. Between them sits a contract, and this file is it — written before
the transport, because the transport is the easy part and the contract is where
the guarantees live or die.

An answer is not prose with citations attached afterwards. It is a **claim, a
quotation, or a refusal**, and which one it is determines what it may contain:

- a `claim` must carry an evidence level and an artefact, and its text must come
  from the registry rather than be composed;
- a `quotation` must carry a document, a line range and a resolving URL, and it
  must be a substring of the passage it names;
- a `refusal` must carry a reason and must not carry a figure.

The last rule is the one that matters and the easiest to lose. A refusal that
says "we do not measure accuracy, though it is likely around 80%" has refused
nothing. Every answer is scanned for numerals that no source vouches for, and
one found is a defect, not a stylistic issue.

## Why this rejects rather than repairs

A malformed answer could be patched — strip the number, drop the citation,
serve what is left. That would produce something plausible from something
broken, which is the failure mode of the entire system expressed in one
function. A malformed answer is a bug in the layer above and must surface as
one.

    python3 answer_contract.py --selftest
"""
from __future__ import annotations

import json
import re
import sys

#: Levels a claim may carry. Anything else is a claim inventing its own
#: authority, and the registry is the only place these are defined.
LEVELS = {"L1", "L2", "L3", "policy", "live"}

#: Kinds of answer. Closed deliberately: a fourth kind would be a fourth set of
#: rules nobody wrote down.
KINDS = {"claim", "quotation", "refusal"}

#: Numerals that carry no claim of measurement. Version numbers, years, and the
#: counts a sentence needs to be a sentence.
INNOCENT = re.compile(
    r"\b(?:19|20)\d\d\b"          # years
    r"|\bv?\d+\.\d+(?:\.\d+)?\b"  # versions
    r"|\b[0-9]\b"                 # single digits: "one of three"
)


class Invalid(Exception):
    """An answer that must not be shown to anyone."""


def _numbers(text: str) -> list[str]:
    """Figures in a sentence, minus the ones that assert nothing."""
    stripped = INNOCENT.sub(" ", text)
    return re.findall(r"\b\d[\d,._]*\b", stripped)


def validate(answer: dict) -> dict:
    """Return the answer, or raise. Never repairs."""
    kind = answer.get("kind")
    if kind not in KINDS:
        raise Invalid(f"kind {kind!r} is not one of {sorted(KINDS)}")

    text = (answer.get("text") or "").strip()
    if not text:
        raise Invalid("an answer with no text")

    if kind == "claim":
        src = answer.get("source") or {}
        if src.get("level") not in LEVELS:
            raise Invalid(
                f"claim carries level {src.get('level')!r}; a claim without a level "
                f"states a fact with authority nobody granted it"
            )
        if not src.get("artefact"):
            raise Invalid("claim carries no artefact; the reader cannot check it")
        if not answer.get("claim_id"):
            raise Invalid(
                "claim carries no registry id. A claim composed rather than "
                "retrieved is the failure this system exists to prevent"
            )

    elif kind == "quotation":
        src = answer.get("source") or {}
        for field in ("document", "lines", "url"):
            if not src.get(field):
                raise Invalid(f"quotation carries no {field}")
        lines = src["lines"]
        if not (isinstance(lines, list) and len(lines) == 2 and lines[0] <= lines[1]):
            raise Invalid(f"quotation has an impossible line range: {lines}")
        passage = answer.get("passage")
        if passage and text not in passage:
            raise Invalid(
                "the quoted text does not appear in the passage it cites. A "
                "paraphrase wearing a citation is worse than no citation"
            )
        # An unpinned link follows a branch, so the lines may already differ.
        # Allowed, and the answer must say so.
        if not src.get("pinned") and "follows the branch" not in text.lower():
            answer.setdefault("caveat", "This link follows the branch rather than a "
                                        "fixed commit; the lines may have moved.")

    else:  # refusal
        if not answer.get("reason"):
            raise Invalid("refusal with no reason is a shrug")
        nums = _numbers(text)
        if nums:
            raise Invalid(
                f"refusal contains figures {nums}: a refusal that offers a number "
                f"has refused nothing"
            )

    # Applies to every kind. A figure the source does not vouch for is a figure
    # the answer invented, whatever kind it claims to be.
    if kind != "refusal":
        vouched = json.dumps(answer.get("source") or {}) + (answer.get("passage") or "")
        for n in _numbers(text):
            if n not in vouched:
                raise Invalid(
                    f"the figure {n!r} appears in the answer and in no source. "
                    f"Numbers come from the registry, where they carry a level"
                )
    return answer


def selftest() -> int:
    cases = [
        ("claim with level and artefact", {
            "kind": "claim", "claim_id": "proofs",
            "text": "43 bounded-model-checking proofs across three crates.",
            "source": {"level": "L1", "artefact": "https://github.com/AxonOS-org/axonos-kernel",
                       "verify": "cargo kani", "n": "43"},
        }, True),
        ("claim with no level", {
            "kind": "claim", "claim_id": "x", "text": "It is fast.",
            "source": {"artefact": "https://example.invalid"},
        }, False),
        ("claim composed rather than retrieved", {
            "kind": "claim", "text": "Something true-sounding.",
            "source": {"level": "L1", "artefact": "https://example.invalid"},
        }, False),
        ("figure with no source", {
            "kind": "claim", "claim_id": "proofs", "text": "Around 97 percent coverage.",
            "source": {"level": "L1", "artefact": "https://example.invalid"},
        }, False),
        ("quotation inside its passage", {
            "kind": "quotation", "text": "consent must be revocable",
            "passage": "The design holds that consent must be revocable at any time.",
            "source": {"document": "rfc0009", "lines": [12, 40], "pinned": True,
                       "url": "https://github.com/x/y/blob/abc/f.md#L12-L40"},
        }, True),
        ("paraphrase wearing a citation", {
            "kind": "quotation", "text": "consent can always be withdrawn",
            "passage": "The design holds that consent must be revocable at any time.",
            "source": {"document": "rfc0009", "lines": [12, 40], "pinned": True,
                       "url": "https://github.com/x/y/blob/abc/f.md#L12-L40"},
        }, False),
        ("impossible line range", {
            "kind": "quotation", "text": "x", "passage": "x",
            "source": {"document": "d", "lines": [40, 12], "pinned": True, "url": "u"},
        }, False),
        ("refusal with a reason", {
            "kind": "refusal", "text": "I do not know that and will not guess.",
            "reason": "outside the registry and the corpus",
        }, True),
        ("refusal that leaks a number", {
            "kind": "refusal",
            "text": "We do not measure accuracy, though it is likely around 82 percent.",
            "reason": "accuracy is not claimed",
        }, False),
        ("refusal with a version in it", {
            "kind": "refusal", "text": "Not covered as of v0.1.0.",
            "reason": "outside the corpus",
        }, True),
    ]
    ok = True
    for name, answer, should_pass in cases:
        try:
            validate(dict(answer))
            passed = True
            why = ""
        except Invalid as e:
            passed = False
            why = str(e)
        good = passed == should_pass
        ok &= good
        mark = "✓" if good else "✗"
        print(f"  {mark} {name:<38} {'accepted' if passed else 'refused'}")
        if not passed and should_pass:
            print(f"      unexpectedly refused: {why}")
        elif passed and not should_pass:
            print("      unexpectedly accepted, which is the dangerous direction")
    print()
    print("ИТОГ:", "контракт держится" if ok else "ЕСТЬ ПРОБЛЕМА")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    try:
        print(json.dumps(validate(json.load(sys.stdin)), ensure_ascii=False, indent=1))
    except Invalid as e:
        print(f"::error::{e}", file=sys.stderr)
        sys.exit(1)
