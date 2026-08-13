# Deploying from a phone

Two things go live: a Worker that answers, and a page that asks. Neither needs
a terminal.

## 1. The Worker

`wrangler` is a Node tool with native dependencies and installing it on Termux
is a gamble that costs an evening. The browser path does the same thing.

**dash.cloudflare.com → Workers & Pages → Create → Create Worker**

Name it `ask-axonos`, create, then **Edit code**. Paste each file:

| Paste into | From |
|:--|:--|
| `index.js` | [`worker/index.js`](worker/index.js) |
| a new file `AGENT_PROMPT.md` | [`worker/AGENT_PROMPT.md`](worker/AGENT_PROMPT.md) |
| a new file `claims.json` | [`worker/claims.json`](worker/claims.json) |
| a new file `corpus-index.json` | [`worker/corpus-index.json`](worker/corpus-index.json) |

Then **Settings → Variables and Secrets → Add**, type **Secret**:

- `ANTHROPIC_API_KEY` — your key

That is the only secret. There is no GitHub token, because the registry and the
prompt are in this repository rather than a private one — a list of what the
project is permitted to assert is stronger published than hidden, and
publishing it removed a token, a fetch on the critical path, and a cache that
could go stale.

**Deploy.** Copy the URL it gives you; it looks like
`https://ask-axonos.<your-subdomain>.workers.dev`.

### Optional: rate limiting

Without it the Worker answers and simply stops counting, which the code
handles. With it, one careless script cannot spend a month of tokens in an
afternoon.

**Workers & Pages → KV → Create namespace**, name it `ASK_KV`, then bind it to
the Worker under **Settings → Bindings → KV namespace**, variable name
`ASK_KV`.

## 2. The page

Open [`site/ask.html`](site/ask.html), find this line near the bottom:

```js
const ENDPOINT = "";
```

Put the Worker URL between the quotes. Then upload `ask.html` to the site the
way you upload everything else.

Without an endpoint the page still works and answers from three hand-written
samples, so a half-finished deploy shows something honest rather than an error.

## 3. Check it

Open the page **on a phone**, tap the input, and watch the panel. That is the
case a `vh` height broke, and the one worth seeing.

Then ask three things:

| Ask | Should |
|:--|:--|
| "how is this verified" | answer with a claim, level `L1`, and a link |
| "what accuracy do you get" | **refuse**, and offer no number |
| "what is the airspeed of a swallow" | say it does not know, and take the question |

If the second one produces a figure, stop and tell me. That is the failure the
whole contract exists to prevent, and it means something upstream is wrong.

---

<sub>© 2026 Denis Yermakou — The AxonOS Project</sub>
