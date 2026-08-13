#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0 OR MIT
# SPDX-FileCopyrightText: 2026 Denis Yermakou <connect@axonos.org>
"""What the agent could not answer, published.

Every project has a list of things it cannot explain about itself. Most keep it
private, discover it late, and learn it from someone who has already decided
not to engage. This one publishes it, and the list is written by whoever asked.

The mechanism is small: the agent already refuses questions outside the
registry and the corpus. Those refusals are the list. Nothing new is inferred —
what is added is that they are counted, deduplicated and shown.

## Three things this must get right, and two of them are not obvious

**Not every refusal is a gap.** "What accuracy does the decoder get" is refused
because accuracy is on the explicit non-claims list — a position the project
holds deliberately. Publishing that as something the project *does not know*
converts a principled stance into a hole, and hands a reader the opposite of
what happened. Refusals are therefore sorted by *why* they were refused, and
only one kind is a gap.

**Questions are about people sometimes.** "My father has ALS, would this help
him" is a fair question and it is not publishable, anonymised or not. The
filter here is deliberately over-broad: a question that might be personal is
dropped rather than published, and losing a real gap costs less than publishing
somebody's circumstances.

**A public list of holes is a target.** One script could fill it with noise and
turn a demonstration of honesty into an argument against the project. So an
entry appears only after being asked by more than one visitor, and near
duplicates collapse into one entry with a count. A gap somebody actually cares
about will be asked twice; a gap invented by a script will not be asked by a
second person.

## What this is not

It is not a support queue and it is not a roadmap. A gap here means one thing:
the agent had nothing to say, and that is a fact about the project's own
documentation rather than a promise to change it.

    python3 gaps.py --record "how does X work" --reason no-source
    python3 gaps.py --publish > docs/GAPS.md
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent
STORE = ROOT / "gaps.json"

#: A refusal is only a gap when it is this kind. The others are the system
#: working: a question the project declines to answer is not a question it
#: cannot answer, and conflating them is the error this classification exists
#: to prevent.
GAP_REASONS = {"no-source", "outside the registry and the corpus", "not in corpus"}

#: Refusals that are positions rather than gaps, with what each one means.
#: Recorded and counted, never published as something unknown.
STANCE_REASONS = {
    "not-claimed": "the project declines to measure this; that is a position, not a gap",
    "rate limited": "an operational limit, unrelated to knowledge",
    "network": "the engine could not be reached",
    "malformed": "the answer failed its own contract, which is a defect in the engine",
}

#: Signals that a question is about a person. Over-broad on purpose.
#:
#: A false positive drops a real gap, which costs a line on a page. A false
#: negative publishes somebody's medical circumstances on a website they cannot
#: edit. The asymmetry is not close, so the filter leans hard one way.
PERSONAL = re.compile(
    r"\b(my|our|his|her|their)\s+(father|mother|dad|mum|mom|son|daughter|wife|"
    r"husband|brother|sister|child|kid|friend|patient|grandfather|grandmother)\b"
    r"|\bi\s+(have|was|am|suffer|got|been)\b"
    r"|\b(diagnos|paraly|stroke|als|sclerosis|epilep|injur|surgery|therapy|"
    r"prognosis|treatment|cure|recover)\w*\b"
    r"|\b(help|save|fix)\s+(me|him|her|them|us)\b",
    re.I,
)

#: Contact details, which must never reach a public file whatever else is true.
CONTACT = re.compile(
    r"[\w.+-]+@[\w-]+\.\w+"                    # e-mail
    r"|\+?\d[\d\s()-]{7,}\d"                   # phone
    r"|\b(?:https?://|www\.)\S+"               # any URL: could be a private doc
    r"|@[A-Za-z0-9_]{3,}",                     # handles
)

#: How many distinct askers before an entry is published.
THRESHOLD = 2

#: Questions longer than this are truncated for display. A wall of text on a
#: public page is somebody pasting something, and pasted text is the most
#: likely place for information nobody meant to share.
MAX_SHOWN = 140


def normalise(q: str) -> str:
    """Collapse a question to what it is asking, for deduplication.

    "How does consent work?" and "how do you do consent" should be one entry.
    Stopwords go, order goes, and what is left is a sorted set of content
    words. Crude, and crude is right: a clustering algorithm nobody can inspect
    would decide what the public list says, and nobody could audit it.
    """
    stop = {
        "how", "does", "do", "you", "your", "the", "a", "an", "is", "are", "what",
        "why", "when", "where", "which", "can", "could", "would", "should", "it",
        "this", "that", "of", "in", "on", "to", "for", "with", "and", "or", "if",
        "there", "any", "some", "about", "me", "my",
    }
    # "work" is not a stopword here, and removing it cost a real case: "how
    # does consent work" collapsed to the single term "consent" and was then
    # dropped as too vague. In this corpus "work" carries the question — how
    # something works is most of what anyone asks — and a stopword list copied
    # from general English discards exactly the verb this domain runs on.
    words = [w for w in re.findall(r"[a-z0-9]+", q.lower()) if w not in stop and len(w) > 2]
    return " ".join(sorted(set(words)))


#: How much two questions must overlap to be treated as one.
#:
#: Exact set equality was the first rule and it was too brittle: "how does
#: consent work" and "how do you do consent" differ by the single word "work"
#: and became two entries, which is how a list of gaps turns into a list of
#: phrasings. Jaccard similarity is coarse and inspectable — someone wondering
#: why two questions merged can count the shared words — and 0.5 was chosen so
#: that two short questions must share most of their content, while a long one
#: is not merged into a short one on a single common noun.
MERGE_AT = 0.5


def similarity(a: str, b: str) -> float:
    """Shared content words over total, both normalised."""
    sa, sb = set(a.split()), set(b.split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def match_existing(question: str, store: dict) -> str | None:
    """The key of an existing entry this question belongs to, if any.

    Compared against every entry rather than by an index, because the list is
    small by design: an entry needs two askers to appear, and a project fields
    tens of distinct questions, not thousands. A structure that scales to
    thousands would be a structure nobody can read, and this file is meant to
    be read.
    """
    k = normalise(question)
    best, score = None, 0.0
    for existing in store.get("gaps", {}):
        s = similarity(k, existing)
        if s > score:
            best, score = existing, s
    return best if score >= MERGE_AT else None


def asker_id(ip_or_token: str) -> str:
    """A stable pseudonym for counting distinct askers.

    Hashed with a fixed salt so the same visitor counts once, and the value in
    the file cannot be reversed into an address. Not a security control: an
    address is not secret and this is not protecting one. It exists so the
    threshold means "two people" rather than "two page loads".
    """
    return hashlib.sha256(f"axonos-gap-v1:{ip_or_token}".encode()).hexdigest()[:12]


def is_publishable(question: str) -> tuple[bool, str]:
    """Whether a question may appear on a public page."""
    if CONTACT.search(question):
        return False, "contains contact details"
    if PERSONAL.search(question):
        return False, "may be about a person"
    if len(question) > 400:
        return False, "long enough to be pasted material"
    # One content word is enough when the question is a real sentence.
    #
    # The first rule demanded two and rejected "how does consent work", which
    # is a fair question with an answer in RFC-0009. Vagueness is better
    # measured by the question than by what survives normalisation: a
    # normaliser exists to group phrasings, and using its output as a quality
    # filter judges the question by how much the grouping threw away.
    if len(normalise(question).split()) < 1 or len(question.split()) < 3:
        return False, "too short to be a gap"
    return True, ""


def record(store: dict, question: str, reason: str, asker: str) -> str:
    """Log one refusal. Returns what happened, for the caller's log."""
    question = " ".join(question.split())
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    if reason in STANCE_REASONS:
        store.setdefault("stances", {}).setdefault(reason, 0)
        store["stances"][reason] += 1
        return f"stance ({reason}), counted and not published"

    if reason not in GAP_REASONS:
        store.setdefault("unclassified", []).append({"reason": reason, "at": now})
        return f"unknown reason {reason!r}; recorded for review, not published"

    ok, why = is_publishable(question)
    if not ok:
        # Counted, never stored. The count is what tells us the filter is doing
        # something; the text is what must not exist in a file that may one day
        # be public.
        store.setdefault("withheld", {}).setdefault(why, 0)
        store["withheld"][why] += 1
        return f"withheld: {why}"

    key = match_existing(question, store) or normalise(question)
    gaps = store.setdefault("gaps", {})
    entry = gaps.setdefault(key, {
        "example": question[:MAX_SHOWN],
        "askers": [],
        "first_seen": now,
        "last_seen": now,
        "resolved": None,
    })
    entry["last_seen"] = now
    if asker not in entry["askers"]:
        entry["askers"].append(asker)
    return f"recorded ({len(entry['askers'])} asker(s))"


def publish(store: dict) -> str:
    """Render the public page. Only entries at or above the threshold."""
    gaps = store.get("gaps", {})
    live = [
        (k, g) for k, g in gaps.items()
        if len(g["askers"]) >= THRESHOLD and not g.get("resolved")
    ]
    closed = [(k, g) for k, g in gaps.items() if g.get("resolved")]
    live.sort(key=lambda kv: (-len(kv[1]["askers"]), kv[1]["first_seen"]))
    closed.sort(key=lambda kv: kv[1].get("resolved", {}).get("at", ""), reverse=True)

    out: list[str] = []
    A = out.append
    A("# What I could not answer")
    A("")
    A("Questions visitors asked that the agent had nothing to say to. This page")
    A("is written by whoever asked, not by us.")
    A("")
    A("Most projects have this list and keep it private, discover it late, and")
    A("hear it from someone who has already decided not to engage. It is more")
    A("useful in the open: a gap here is a fact about this project's own")
    A("documentation, and it is the shortest description of what to write next.")
    A("")
    A("A question appears after two different people ask it. One person asking")
    A("something is a question; two is a gap. Questions that might be about a")
    A("person, or that carry contact details, are never published — the filter")
    A("is deliberately over-broad, and losing a real gap costs less than")
    A("publishing somebody's circumstances.")
    A("")
    A("**Refusals that are not gaps are not here.** The agent declines to state")
    A("a classification accuracy because accuracy is on the explicit non-claims")
    A("list. That is a position the project holds, not something it does not")
    A("know, and putting it on this page would turn one into the other.")
    A("")
    A("---")
    A("")

    if live:
        A("## Open")
        A("")
        A("| Asked | Times | First asked |")
        A("|:--|--:|:--|")
        for _, g in live:
            A(f"| {g['example']} | {len(g['askers'])} | {g['first_seen'][:10]} |")
        A("")
    else:
        A("## Open")
        A("")
        A("Nothing yet. Either the agent has answered everything asked of it, or")
        A("not enough people have asked. Both are possible and this page does not")
        A("distinguish them, which is worth knowing when reading an empty list.")
        A("")

    if closed:
        A("## Closed")
        A("")
        A("| Was asked | Answered | Where |")
        A("|:--|:--|:--|")
        for _, g in closed:
            r = g["resolved"]
            A(f"| {g['example']} | {r.get('at', '')[:10]} | {r.get('where', '')} |")
        A("")

    stances = store.get("stances", {})
    if stances:
        A("## Declined, and why")
        A("")
        A("Refusals that are positions rather than gaps. Counted here so the")
        A("distinction is visible rather than asserted.")
        A("")
        A("| Reason | Times | What it means |")
        A("|:--|--:|:--|")
        for reason, n in sorted(stances.items(), key=lambda kv: -kv[1]):
            A(f"| `{reason}` | {n} | {STANCE_REASONS.get(reason, '')} |")
        A("")

    withheld = sum(store.get("withheld", {}).values())
    if withheld:
        A(f"<sub>{withheld} question(s) were withheld from this page: they")
        A("mentioned a person or carried contact details. They are counted and")
        A("their text is not stored.</sub>")
        A("")

    A("---")
    A("")
    A("<sub>Generated from the agent's own refusals. "
      f"Last built {datetime.now(timezone.utc).strftime('%Y-%m-%d')}. "
      "© 2026 Denis Yermakou — The AxonOS Project</sub>")
    return "\n".join(out) + "\n"


def load() -> dict:
    try:
        return json.loads(STORE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def save(store: dict) -> None:
    STORE.write_text(json.dumps(store, ensure_ascii=False, indent=1), encoding="utf-8")


def selftest() -> int:
    cases = [
        ("plain gap", "how does the scheduler handle priority inversion", "no-source", True),
        ("family", "my father has ALS, would this help him", "no-source", False),
        ("first person medical", "i have a spinal cord injury, can I use this", "no-source", False),
        ("email in question", "write to me at someone@example.com about the SDK", "no-source", False),
        ("URL in question", "what about https://internal.example.com/doc", "no-source", False),
        ("phone", "call me on +1 555 0100 to discuss", "no-source", False),
        ("too short", "what", "no-source", False),
        ("one content word is enough", "how does consent work", "no-source", True),
        ("stance is not a gap", "what accuracy does the decoder get", "not-claimed", False),
        ("clinical word", "does this cure paralysis", "no-source", False),
    ]
    ok = True
    for name, q, reason, should_publish in cases:
        store: dict = {}
        record(store, q, reason, asker_id("a"))
        published = bool(store.get("gaps"))
        good = published == should_publish
        ok &= good
        print(f"  {'✓' if good else '✗'} {name:<26} "
              f"{'recorded' if published else 'withheld'}")

    # Threshold: one asker is not a gap, two are.
    store = {}
    record(store, "how does the relay path sign commits", "no-source", asker_id("a"))
    one = len(publish(store).split("Nothing yet")) > 1
    record(store, "how do you sign commits in the relay path", "no-source", asker_id("b"))
    two = "Nothing yet" not in publish(store)
    ok &= one and two
    print(f"  {'✓' if one and two else '✗'} threshold                  "
          f"one asker hidden, two shown")

    # Deduplication: two phrasings of one question are one entry.
    store = {}
    record(store, "How does consent work?", "no-source", asker_id("a"))
    record(store, "how do you do consent", "no-source", asker_id("b"))
    dedup = len(store.get("gaps", {})) == 1
    ok &= dedup
    print(f"  {'✓' if dedup else '✗'} deduplication              "
          f"{len(store.get('gaps', {}))} entry from two phrasings")

    print()
    print("ИТОГ:", "фильтры держатся" if ok else "ЕСТЬ ПРОБЛЕМА")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--record", metavar="QUESTION")
    ap.add_argument("--reason", default="no-source")
    ap.add_argument("--asker", default="anonymous")
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    store = load()
    if args.record:
        print("  " + record(store, args.record, args.reason, asker_id(args.asker)))
        save(store)
        return 0
    if args.publish:
        print(publish(store))
        return 0
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
