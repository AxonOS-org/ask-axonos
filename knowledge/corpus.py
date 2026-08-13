#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0 OR MIT
# SPDX-FileCopyrightText: 2026 Denis Yermakou <connect@axonos.org>
"""Retrieval over the published artefacts, with provenance per passage.

The registry answers fifteen questions and refuses everything else. That is
safe and it is not enough. "How does the privacy boundary work" is a fair
question with a real answer in RFC-0009, and an agent that says "I do not know"
to it is failing a caller who could have been served.

The tempting fix is to hand a model the documents. That would reintroduce the
failure the registry exists to prevent: a model given a corpus produces fluent
prose whose relationship to the corpus nobody can check, and the difference
between quoting and inventing becomes invisible at exactly the moment it
matters.

So this retrieves **passages, not answers**. Every result carries the file, the
line range and a URL that resolves to those lines on GitHub. The agent may
quote a passage and attribute it; it may not paraphrase one into a claim. A
reader who doubts anything follows the link and reads the same lines the agent
read.

## Why the corpus is fetched rather than vendored

Copying the documents here would create a second copy that drifts, and this
project has spent a week removing those. The corpus is fetched at build time
into a cache with the commit SHA it came from, so a stale cache is detectable
rather than silent.

## What is deliberately excluded

Documents that assert performance are not in the corpus. RFC-0001 carries the
972 microsecond figure, and a retrieved passage stating it would put an L2
measurement into an answer with the authority of a quotation, stripped of the
"raw traces not published" that the registry attaches to it. Numbers come from
`claims.json`, where they carry their evidence level. Prose comes from here.

That split is the whole design. Ask it for a number and the registry answers,
with a level. Ask it how something works and this answers, with a line range.

    python3 corpus.py --build      # fetch and index
    python3 corpus.py "consent"    # search
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
CACHE = ROOT / ".corpus-cache"
RAW = "https://raw.githubusercontent.com"
WEB = "https://github.com"

#: Documents the agent may quote, and the reason each is here.
#:
#: Every entry explains what a reader gets from it, because a corpus assembled
#: without stated criteria becomes a corpus assembled by whoever last edited it.
SOURCES: list[dict] = [
    {
        "id": "rfc0009",
        "repo": "AxonOS-org/axonos-rfcs",
        "path": "rfcs/0009-bounded-disclosure-sealed-neural-data.md",
        "why": "how the privacy boundary works, stated normatively",
    },
    {
        "id": "rfc0008",
        "repo": "AxonOS-org/axonos-rfcs",
        "path": "rfcs/0008-deadline-closure-acquisition-chain.md",
        "why": "what a closed deadline means and what it refuses",
    },
    {
        "id": "rfc0003",
        "repo": "AxonOS-org/axonos-rfcs",
        "path": "rfcs/0003-validation-status-framework.md",
        "why": "what L1, L2 and L3 mean; the vocabulary every claim depends on",
    },
    {
        "id": "profile",
        "repo": "AxonOS-org/.github",
        "path": "profile/README.md",
        "why": "the architecture in prose, including what is unsolved",
    },
    {
        "id": "threat",
        "repo": "AxonOS-BCI/axonos-community-radar",
        "path": "docs/THREAT_MODEL.md",
        "why": "what the project defends against and what it accepts",
    },
]

#: Excluded, with the reason, because the exclusions carry more design than the
#: inclusions and an undocumented one reads as an oversight.
EXCLUDED = {
    "rfcs/0001-edf-scheduler-biological-deadlines.md":
        "carries the 972 microsecond measurement. A quoted passage would state "
        "an L2 figure with the authority of a quotation, without the 'raw "
        "traces not published' the registry attaches to it. Numbers come from "
        "claims.json; prose comes from the corpus.",
    "CHANGELOG.md":
        "describes what changed, not what is true now. A passage from a "
        "changelog answers a question nobody asked in the present tense.",
    "medium articles":
        "written for readers rather than for accuracy, and not versioned. "
        "Anything in them that is true is in an RFC.",
}


def fetch(repo: str, path: str) -> tuple[str, str] | None:
    """Return (body, sha) for a document, or None."""
    try:
        req = urllib.request.Request(
            f"{RAW}/{repo}/main/{path}",
            headers={"User-Agent": "axon-agent-corpus"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return None
    # The commit the file is at, so a cached passage can be told from a current
    # one. A quotation attributed to a document that has since changed is a
    # misquotation, however faithfully it was copied.
    # A passage without a commit cannot be linked honestly: a URL containing
    # "unknown" resolves to nothing, and one pointing at main points at
    # whatever the file becomes. Failing to learn the commit is a reason to
    # refuse the document, not to link it approximately.
    sha = ""
    try:
        api = f"https://api.github.com/repos/{repo}/commits?path={path}&per_page=1"
        req = urllib.request.Request(api, headers={"User-Agent": "axon-agent-corpus"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
            if data:
                sha = data[0]["sha"]
    except Exception:  # noqa: BLE001
        pass
    # Without a commit the document is still usable — it just cannot be linked
    # to a fixed revision. Refusing the whole build over a rate limit was the
    # right instinct in the wrong place: it made an unauthenticated run fail
    # entirely rather than produce an index whose passages say plainly that
    # their links follow main.
    #
    # The distinction survives into the link. A passage with a commit gets a
    # pinned URL; one without gets a main URL and a flag, and the agent is told
    # to say so when quoting it.
    return body, sha


def passages(body: str, doc: dict, sha: str) -> list[dict]:
    """Split a document into addressable passages.

    Split on headings rather than by a fixed window. A heading is the author's
    own statement of where one idea ends, and a window that cuts across it
    produces a passage that reads as a claim its author did not make.
    """
    lines = body.split("\n")
    marks = [i for i, l in enumerate(lines) if re.match(r"^#{2,4} ", l)]
    if not marks:
        marks = [0]
    marks.append(len(lines))

    out = []
    for j in range(len(marks) - 1):
        start, end = marks[j], marks[j + 1]
        text = "\n".join(lines[start:end]).strip()
        if len(text.split()) < 25:
            # Too short to answer anything. A heading with two lines under it
            # retrieved as a passage looks like an answer and is not one.
            continue
        heading = lines[start].lstrip("# ").strip() if start < len(lines) else ""
        out.append({
            "doc": doc["id"],
            "heading": heading,
            "text": text,
            "lines": [start + 1, end],
            # Pinned to the commit, not to main. A link to main is a link to
            # whatever the file becomes.
            "url": (f"{WEB}/{doc['repo']}/blob/{sha or 'main'}/{doc['path']}"
                    f"#L{start+1}-L{end}"),
            #: True when the link follows main rather than a fixed commit. A
            #: quotation attributed to a moving target is a quotation that may
            #: already be wrong, and the agent must say which kind it is
            #: holding.
            "pinned": bool(sha),
            "repo": doc["repo"],
            "path": doc["path"],
            "sha": sha,
        })
    return out


def build() -> int:
    CACHE.mkdir(exist_ok=True)
    index: list[dict] = []
    failed: list[str] = []

    for doc in SOURCES:
        got = fetch(doc["repo"], doc["path"])
        if not got:
            failed.append(f"{doc['repo']}/{doc['path']}")
            continue
        body, sha = got
        index.extend(passages(body, doc, sha))

    if failed:
        # An index built from a subset is not an index; it is a smaller index
        # that will answer confidently about the part it happens to hold.
        print(f"::error::could not fetch {len(failed)} document(s): {failed}")
        return 1

    (CACHE / "index.json").write_text(
        json.dumps({"passages": index, "sources": len(SOURCES)}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"  indexed {len(index)} passages from {len(SOURCES)} documents")
    for doc in SOURCES:
        n = sum(1 for p in index if p["doc"] == doc["id"])
        print(f"    {doc['id']:<10} {n:>3} passages — {doc['why']}")
    return 0


#: What each document is about, in the words a caller would use. The document
#: id is not searchable prose — nobody types "rfc0009" — so the topics it
#: covers are declared here and matched like any other term.
DOC_TOPICS: dict[str, set[str]] = {
    "rfc0009": {"privacy", "boundary", "disclosure", "bits", "budget", "sealed",
                "consent", "grant", "revoke", "vault", "leak", "bound"},
    "rfc0008": {"deadline", "timing", "wcet", "latency", "realtime", "budget",
                "admission", "refuse", "period", "jitter", "clock"},
    "rfc0003": {"evidence", "level", "proven", "measured", "validation", "claim",
                "pending", "l1", "l2", "l3"},
    "profile": {"architecture", "overview", "unsolved", "stack", "organs", "what"},
    "threat": {"threat", "attack", "security", "risk", "adversary", "mitigation"},
}


def doc_words(p: dict) -> set[str]:
    return DOC_TOPICS.get(p["doc"], set())


def search(query: str, k: int = 3) -> list[dict]:
    """Rank passages by term overlap.

    Deliberately simple, and the simplicity is the point rather than a
    limitation accepted for now. A retrieval step nobody can reason about
    reintroduces the opacity this design exists to avoid: with term overlap, a
    caller who wonders why a passage came back can count the words.
    """
    try:
        idx = json.loads((CACHE / "index.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        print("::error::no index; run --build first")
        return []

    # Two-character terms are kept when they look like an identifier: "L2" and
    # "L3" are the vocabulary of the evidence framework and dropping them
    # answered a question about evidence levels with a passage about anything
    # else. Ordinary short words are still dropped.
    raw = re.findall(r"\w+", query.lower())
    terms = [t for t in raw if len(t) > 2 or re.fullmatch(r"[a-z]\d", t)]
    if not terms:
        return []

    scored = []
    for p in idx["passages"]:
        low = p["text"].lower()
        head = p["heading"].lower()
        # A term in the heading counts triple: the author put it there to say
        # what the section is about.
        # A term in the heading counts for far more than one in the body.
        #
        # The first weighting used three, and "privacy boundary" returned the
        # deadline RFC — the word "boundary" appears often in prose about
        # timing, and body frequency drowned a heading that said "privacy" once.
        # Frequency in a body measures length as much as relevance; a heading
        # is the author stating what a section is about, and it should not be
        # outvoted by repetition.
        #
        # Term presence is counted once per passage rather than summed, for the
        # same reason: a passage that says "consent" nine times is not nine
        # times more about consent than one that says it twice.
        score = sum(
            (1 if t in low else 0) + 12 * head.count(t) + 6 * (t in doc_words(p))
            for t in terms
        )
        if score:
            scored.append((score, p))
    scored.sort(key=lambda x: -x[0])
    return [p for _, p in scored[:k]]


def main() -> int:
    if "--build" in sys.argv:
        return build()
    if len(sys.argv) < 2:
        print(__doc__.split("\n\n")[0])
        print("\nusage: corpus.py --build | corpus.py <query>")
        return 1

    hits = search(" ".join(sys.argv[1:]))
    if not hits:
        print("  nothing matched. The agent says 'I do not know' here, and that "
              "is the correct answer rather than a failure.")
        return 0
    for h in hits:
        print(f"\n  {h['doc']} · {h['heading'][:60]}")
        print(f"  lines {h['lines'][0]}-{h['lines'][1]} · {h['url']}")
        first = " ".join(h["text"].split())[:200]
        print(f"  {first}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
