# The engine

Runs on Cloudflare Workers. The browser sends a question and receives an answer
that has already been validated; it never sees a key, the registry, or a
document.

## Deploy

```sh
npm install -g wrangler
wrangler login

# Secrets go into Cloudflare, never into a repository.
wrangler secret put ANTHROPIC_API_KEY
wrangler secret put GITHUB_READ_TOKEN     # contents:read on axonos-agent, nothing else

wrangler deploy
```

Then point the widget at the deployed URL.

## Why the secrets are not in the private repository

A private repository is a commercial boundary, not a vault. A key committed to
one has still been committed: repositories get cloned to laptops, shared with
contractors, restored from backups, and made public by a mis-click. Visibility
is a setting; a leaked key is permanent.

`wrangler secret put` places the value in Cloudflare's store. The code names the
variable and never contains the value, so this file can be public without
consequence — and it is.

## What the engine will not do

**It does not compose answers.** A model that writes a sentence about AxonOS is
a model that can write one AxonOS cannot support. It is handed a closed set of
material and one job: choose which of it answers the question.

**It does not repair a bad answer.** Stripping an unsupported figure and serving
what remains would produce something plausible out of something broken. A
failing answer becomes a refusal, and the refusal says what failed.

**It does not vendor the prompt.** The system prompt is fetched from the private
repository at request time, because a copy drifts from the registry that
generates it. A failure to fetch is a failure to answer: answering from a stale
prompt is worse than not answering.

## The one duplication this project accepts

The contract is enforced twice: in `contract/answer_contract.py`, which is the
specification and is testable, and in `worker/index.js`, which is the gate the
bytes actually pass through.

A guarantee that lives only in a file nothing calls at request time is a
guarantee about a document.

---

<sub>© 2026 Denis Yermakou — The AxonOS Project</sub>
