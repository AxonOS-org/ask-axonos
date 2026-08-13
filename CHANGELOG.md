# Changelog

## [0.5.0] — 2026-08-13

### Added
- **`site/ask.html`** — the page, not just the widget. Open Graph tags, because
  the link gets pasted where a card renders and a card with a truncated title
  reads as an afterthought. The widget's styles are included rather than
  copied, so a fix is a fix in both.
- **`DEPLOY.md`** — the browser path. `wrangler` is a Node tool with native
  dependencies and installing it on Termux is a gamble that costs an evening;
  the Cloudflare dashboard does the same thing from a phone. It ends with three
  questions to ask the live agent, and the middle one must be refused: if it
  produces an accuracy figure, the contract has failed.
- **`knowledge/`** — the registry, its validators, the prompt generated from
  it, and retrieval with provenance per passage.

### Changed
- **The registry and prompt are public and bundled into the Worker.** They were
  private and fetched with a read token at request time. That worked and bought
  nothing: a registry is a list of what this project is permitted to assert,
  with the check for each, and it is stronger published than hidden — a claim
  nobody can fake is worth nothing if nobody can read it.

  Publishing removed three things rather than solving one: a token living in
  the cloud, a fetch on the critical path of every answer, and a cache that
  could go stale. `ANTHROPIC_API_KEY` is now the only secret.

- **Attribution reaches every file.** Six carried none: the changelog, two
  copies of the registry, the Worker configuration, the page, and the registry
  self-test. JSON takes no comments, so the registries carry `author`,
  `copyright` and `license` as fields, ordered first so they are read before
  the content they cover. The page carries a visible footer as well as a
  comment — a licence a reader cannot see is a licence a reader will not check.

### Notes
The attribution audit produced one false positive worth recording. It reported
`CITATION.cff` as unattributed while the file names the author correctly in
separate `family-names` and `given-names` fields, which is what the format
requires. The check was looking for one string in a file that stores two, and
the file was right.

## [0.4.0] — 2026-08-11

### Changed
- **The registry, the prompt and the corpus index are public.** They were in a
  private repository and the Worker fetched them with a read token at request
  time. That worked and bought nothing.

  A registry is a list of what this project is permitted to assert, with the
  check for each. It is stronger published than hidden: a claim nobody can fake
  is worth nothing if nobody can read it. Publishing it removed a token living
  in the cloud, a fetch on the critical path of every answer, and a cache that
  could go stale — three problems deleted rather than solved.

  What stays private is what genuinely is: the strategy and the correspondence.

### Added
- `site/ask.html` — the page, not just the widget. Open Graph tags because the
  link will be pasted where a card renders, and a card with a truncated title
  reads as an afterthought. The widget's own styles are included rather than
  copied, so a fix is a fix in both.
- `DEPLOY.md` — the browser path. `wrangler` is a Node tool with native
  dependencies and installing it on Termux is a gamble that costs an evening;
  the Cloudflare dashboard does the same thing from a phone.
- A three-question check at the end of the deploy notes. The middle one asks
  for an accuracy figure and must be refused; if it produces a number, the
  contract has failed and something upstream is wrong.

## [0.3.0] — 2026-08-11

### Added
- **`contract/gaps.py` — the questions this agent could not answer, published.**

  Every project has a list of things it cannot explain about itself. Most keep
  it private, discover it late, and hear it from someone who has already
  decided not to engage. This one publishes it, and the list is written by
  whoever asked.

  Three things it has to get right, and two are not obvious.

  **Not every refusal is a gap.** "What accuracy does the decoder get" is
  refused because accuracy is on the explicit non-claims list, a position the
  project holds. Publishing it as something unknown converts a stance into a
  hole. Refusals are sorted by why, and only one kind reaches the page.

  **Questions are about people sometimes.** "My father has ALS, would this help
  him" is fair and unpublishable, anonymised or not. The filter is deliberately
  over-broad: losing a real gap costs a line on a page, publishing somebody's
  circumstances costs more.

  **A public list of holes is a target.** An entry appears after two different
  people ask. A gap somebody cares about will be asked twice; one invented by a
  script will not be.

- The Worker records refusals with a hashed asker id and a ninety-day expiry.
  What may be stored is decided by `gaps.py`, so contact details and anything
  that might be about a person never reach storage.

### Fixed while building it
- The stopword list contained `work`, so "how does consent work" collapsed to a
  single term and was dropped as too vague. A list copied from general English
  discarded the verb this domain runs on: how something works is most of what
  anyone asks.
- Grouping used exact set equality, so two phrasings of one question became two
  entries — which is how a list of gaps turns into a list of phrasings. It is
  Jaccard similarity at 0.5 now: coarse, inspectable, and it keeps "consent
  work" apart from "scheduler work" at 0.33 while merging the phrasings.
- Vagueness was measured on the normaliser's output, which judged a question by
  how much the grouping threw away. It is measured on the question.

## [0.2.0] — 2026-08-11

### Added
- **`contract/answer_contract.py` — the shape an answer must have.** Written
  before the transport, because the transport is the easy part and the contract
  is where the guarantees live or die.

  An answer is a claim, a quotation or a refusal, and which one determines what
  it may contain. A claim must carry an evidence level and a registry id, so a
  composed sentence cannot pass as a retrieved one. A quotation must be a
  substring of the passage it cites, so a paraphrase cannot wear a citation. A
  refusal must not contain a figure, because *"we do not measure accuracy,
  though it is likely around 82 percent"* has refused nothing.

  It rejects rather than repairs. Stripping the number and serving what remains
  would produce something plausible from something broken, which is this
  system's failure mode expressed in one function.

  Ten self-test cases, each a way an answer can be wrong.

- **Speech, offered and never imposed.** A Listen control appears only where the
  browser supports it, stays off until asked, and announces whose voice it is
  before it says anything: synthesised from Denis's own, and he is not on the
  line. A synthesised voice built from a person's own and used without saying so
  is exactly what this project argues against.

  Everything spoken stays on screen. Source blocks are not read aloud, because a
  URL spoken character by character is noise and the link belongs where it can
  be clicked.

### Changed
- The opening line now says **digital assistant**. Same disclosure, plainer word.

### Fixed
- Five defects, the first visible only on a phone. The log was sized in `vh`, so
  the on-screen keyboard shrank the viewport and collapsed the panel at the
  moment someone tapped the input; it is `dvh` now with `vh` as a fallback.
  Escape did not close the panel, leaving a mouse as the only way out. A heading
  inside the button meant a screen reader navigating headings landed inside a
  control it could not read out of. `aria-live` sat on the whole panel, so
  opening it announced everything rather than the new message. And nothing
  honoured `prefers-reduced-motion`.

## [0.1.0] — 2026-08-11

### Added
- The widget: a button and a panel, one file, no dependencies.

  The button is not a corner bubble on purpose. A bubble reads as support chat,
  and a visitor reading it that way will not ask the question this exists to
  answer. It states the offer in full and is large enough to be read before it
  is clicked.

  Provenance is rendered at the same weight as the sentence it supports. A
  claim shows its evidence level, a quotation shows its line range, a refusal
  shows why. A claim without its level is the thing this system exists to
  prevent, so it is not a footnote.

- Disclosure in the first line, unprompted. This project builds a control layer
  for trusted AI agents; one concealing what it is would refute the product by
  existing.

### Notes
The three replies are hand-written. Wiring the real backend replaces `reply()`
and nothing else: the rendering, the provenance blocks and the refusal path are
already the shapes the knowledge system produces.

No inline styles. A strict `Content-Security-Policy` with `style-src 'self'`
drops them silently, which would leave an answer unstyled on the live site
while looking correct locally. The radar shipped that exact defect a week ago.

---

<sub>SPDX-License-Identifier: Apache-2.0 OR MIT · Copyright (c) 2026 Denis Yermakou <connect@axonos.org> — The AxonOS Project · https://axonos.org</sub>
