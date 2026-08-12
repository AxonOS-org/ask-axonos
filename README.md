<div align="center">

# ask-axonos

### An answer, and where it came from.

[![Version](https://img.shields.io/badge/version-0.2.0-2dd4ff?style=flat-square&labelColor=0e141d)](CHANGELOG.md)
[![Dependencies](https://img.shields.io/badge/dependencies-0-34d399?style=flat-square&labelColor=0e141d)](src/widget.html)
[![Discloses](https://img.shields.io/badge/discloses%20itself-first%20line-a78bfa?style=flat-square&labelColor=0e141d)](#it-says-what-it-is-before-being-asked)
[![License](https://img.shields.io/badge/Apache--2.0%20OR%20MIT-6b7789?style=flat-square&labelColor=0e141d)](#licence)

**[→ Open the preview](https://github.com/AxonOS-org/ask-axonos/blob/main/src/widget.html)** · one file, no build step

</div>

---

A visitor arrives at a page making unusual claims: a timing budget that refuses
configurations instead of monitoring them, an information bound on what an
application may learn about sealed data, forty-three machine-checked proofs.
Scepticism is the correct response, and until now the only way to act on it was
to read a great deal.

This is the shorter path. Ask, and get the source with the answer.

## What an answer looks like

Three kinds, and the widget shows which kind it is giving you.

| | Comes from | Carries |
|:--|:--|:--|
| **A claim** | the registry of statements this project may make | the level at which it is evidenced, and the artefact that shows it |
| **A quotation** | the published specifications | the file, the line range, and a link that resolves to those lines |
| **"I do not know"** | neither | the reason, and where the question goes instead |

The third is not a failure mode. A question outside the registry and the corpus
gets a refusal rather than a guess, because a gap reported is useful and a gap
filled is a defect that reaches whoever asked.

**Numbers never come from a quotation.** Every figure comes from the registry,
where it carries its evidence level. A number lifted out of a document arrives
with the authority of a quotation and without the qualification attached to it,
which is how a measurement becomes a proof in somebody's notes.

## It says what it is before being asked

The first line of every conversation states that this is an AI representative
and not a person. That is not a legal formality bolted on afterwards.

This project builds a control layer for trusted AI agents. An agent that
concealed what it is would refute the product by existing. Said plainly, it
demonstrates it.

## Why the button reads the way it does

Not a bubble in the corner. A bubble is the universal signal for support chat,
and a visitor who reads it that way will not ask the question this exists to
answer. It sits in the page, states the whole offer, and is large enough to be
read before it is clicked.

It does not say "chat", which describes a mechanism. It says what the visitor
gets: any question, an answer with its source, and a refusal instead of a guess.

## What is here, and what is not

**Here.** The widget: one HTML file, no framework, no build step, no
third-party script, no inline styles. A page enforcing a strict
`Content-Security-Policy` drops inline styles silently, and an answer would
render unstyled on the live site while looking correct in a local file.

**Not here yet.** The backend. The three replies in the preview are
hand-written to show each kind of answer. Wiring it to the knowledge system
replaces one function and nothing else.

The knowledge system itself, the registry and its validators and the retrieval
with provenance per passage, lives in a private repository because it holds the
working analysis this project is steered by. What it produces is public: every
claim it may make traces to an artefact anyone can open.

## The contract between widget and backend

`contract/answer_contract.py` defines what an answer may be and refuses one that
is not. It is here rather than in the private repository because it is the
guarantee a visitor is being offered, and a guarantee nobody can read is a
promise.

It rejects rather than repairs. A malformed answer could be patched — strip the
figure, drop the citation, serve what is left — and that would produce something
plausible from something broken, which is this system's failure mode expressed
in one function.

## Licence

Apache-2.0 OR MIT.

---

<div align="center">

**© 2026 Denis Yermakou** — authored for The AxonOS Project

[axonos.org](https://axonos.org) · connect@axonos.org

</div>
