# Changelog

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
