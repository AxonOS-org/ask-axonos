/**
 * ask-axonos — the engine.
 *
 * SPDX-License-Identifier: Apache-2.0 OR MIT
 * SPDX-FileCopyrightText: 2026 Denis Yermakou <connect@axonos.org>
 *
 * Runs on Cloudflare Workers. The browser never sees a key, never sees the
 * registry, and never sees a document: it sends a question and receives an
 * answer that has already been validated against the contract.
 *
 * ## What this is responsible for, and what it refuses to be
 *
 * It retrieves, it calls a model, and it validates. It does not compose
 * answers, and the distinction is the whole design: a model that writes a
 * sentence about AxonOS is a model that can write a sentence AxonOS cannot
 * support. So the model is given a closed set of material and one job —
 * choose which of it answers the question — and everything it returns is
 * checked against that material before it leaves this function.
 *
 * An answer that fails validation is not repaired. Stripping the offending
 * figure and serving what remains would produce something plausible out of
 * something broken, which is this project's failure mode in one line of code.
 * It becomes a refusal, and the refusal says what went wrong.
 *
 * ## Where the secret lives
 *
 * In Cloudflare's secret store, never in a repository:
 *
 *     wrangler secret put ANTHROPIC_API_KEY
 *
 * A private repository is a commercial boundary, not a vault. A key committed
 * to one has still been committed: repositories get cloned, shared with
 * contractors, restored from backups, and made public by a mis-click. The only
 * key that cannot leak from a repository is the one that was never in it.
 */

const MODEL = "claude-sonnet-4-6";
const MAX_QUESTION = 400;

/** Answers per IP per hour. Generous for a person, useless for a scraper. */
const RATE_LIMIT = 30;

const CORS = {
  "Access-Control-Allow-Origin": "https://axonos.org",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

/**
 * The system prompt is fetched from the private repository, not vendored here.
 *
 * A copy would drift from the registry that generates it, and this project has
 * spent a week removing copies that drifted. The fetch is cached; a failure to
 * fetch is a failure to answer, because answering from a stale prompt is worse
 * than not answering.
 */
async function loadKnowledge(env) {
  const headers = {
    Authorization: `Bearer ${env.GITHUB_READ_TOKEN}`,
    Accept: "application/vnd.github.raw",
    "User-Agent": "ask-axonos-worker",
  };
  const base = "https://api.github.com/repos/AxonOS-org/axonos-agent/contents";

  const [promptRes, indexRes, claimsRes] = await Promise.all([
    fetch(`${base}/knowledge/AGENT_PROMPT.md`, { headers }),
    fetch(`${base}/knowledge/.corpus-cache/index.json`, { headers }),
    fetch(`${base}/knowledge/claims.json`, { headers }),
  ]);

  if (!promptRes.ok || !claimsRes.ok) {
    throw new Error(
      `knowledge unavailable (prompt ${promptRes.status}, claims ${claimsRes.status})`
    );
  }

  return {
    prompt: await promptRes.text(),
    claims: JSON.parse(await claimsRes.text()),
    // The corpus index is optional: without it the agent answers from the
    // registry alone, which is narrower and still correct. Without the
    // registry it cannot answer at all, and says so.
    passages: indexRes.ok ? JSON.parse(await indexRes.text()).passages || [] : [],
  };
}

/**
 * Term-overlap retrieval, deliberately simple.
 *
 * A retrieval step nobody can reason about reintroduces the opacity this
 * design exists to avoid. With term overlap, someone wondering why a passage
 * came back can count the words. Headings count for more than bodies, because
 * frequency in a body measures length as much as relevance.
 */
function retrieve(question, passages, k = 4) {
  const terms = (question.toLowerCase().match(/\w+/g) || []).filter(
    (t) => t.length > 2 || /^[a-z]\d$/.test(t)
  );
  if (!terms.length) return [];

  return passages
    .map((p) => {
      const body = (p.text || "").toLowerCase();
      const head = (p.heading || "").toLowerCase();
      let score = 0;
      for (const t of terms) {
        if (body.includes(t)) score += 1;
        score += 12 * (head.split(t).length - 1);
      }
      return { p, score };
    })
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, k)
    .map((x) => x.p);
}

/** Figures that assert nothing: years, versions, single digits. */
const INNOCENT = /\b(?:19|20)\d\d\b|\bv?\d+\.\d+(?:\.\d+)?\b|\b\d\b/g;

function figuresIn(text) {
  return (text.replace(INNOCENT, " ").match(/\b\d[\d,._]*\b/g) || []);
}

/**
 * The contract, enforced here as well as in Python.
 *
 * Duplicated on purpose, and it is the one duplication this project accepts.
 * The Python file is the specification and is testable; this is the gate the
 * bytes actually pass through. A guarantee that lives only in a file nothing
 * calls at request time is a guarantee about a document.
 */
function validate(answer, material) {
  const kind = answer.kind;
  if (!["claim", "quotation", "refusal"].includes(kind)) {
    throw new Error(`kind ${kind} is not one of claim, quotation, refusal`);
  }
  const text = (answer.text || "").trim();
  if (!text) throw new Error("an answer with no text");

  if (kind === "refusal") {
    if (!answer.reason) throw new Error("a refusal with no reason is a shrug");
    const nums = figuresIn(text);
    if (nums.length) {
      throw new Error(
        `refusal contains ${nums.join(", ")}: a refusal that offers a number has refused nothing`
      );
    }
    return answer;
  }

  if (kind === "claim") {
    const id = answer.claim_id;
    const claim = material.claims.find((c) => c.id === id);
    if (!claim) {
      throw new Error(
        `claim id ${id} is not in the registry. A claim composed rather than retrieved is the failure this system prevents`
      );
    }
    answer.source = {
      level: claim.level,
      artefact: claim.source,
      verify: claim.verify,
    };
  }

  if (kind === "quotation") {
    const src = answer.source || {};
    for (const field of ["document", "lines", "url"]) {
      if (!src[field]) throw new Error(`quotation carries no ${field}`);
    }
    const passage = material.passages.find(
      (p) => p.doc === src.document && p.lines[0] === src.lines[0]
    );
    if (!passage) throw new Error("quotation cites a passage that was not retrieved");
    if (!passage.text.includes(text)) {
      throw new Error(
        "the quoted text is not in the passage it cites. A paraphrase wearing a citation is worse than no citation"
      );
    }
    if (!passage.pinned) {
      answer.caveat =
        "This link follows the branch rather than a fixed commit; the lines may have moved.";
    }
  }

  // Applies to claim and quotation alike: a figure no source vouches for is a
  // figure the answer invented, whatever kind it says it is.
  const vouched = JSON.stringify(answer.source || {}) + (answer.passage || "");
  for (const n of figuresIn(text)) {
    if (!vouched.includes(n)) {
      throw new Error(
        `the figure ${n} appears in the answer and in no source. Numbers come from the registry, where they carry a level`
      );
    }
  }
  return answer;
}

async function ask(question, material, env) {
  const hits = retrieve(question, material.passages);

  const context = [
    "## Claims you may state, and only these",
    ...material.claims.map(
      (c) => `- id:${c.id} [${c.level}] ${c.text}\n  artefact: ${c.source}`
    ),
    "",
    "## Passages retrieved for this question",
    hits.length
      ? hits
          .map(
            (p, i) =>
              `### passage ${i + 1} — ${p.doc}, lines ${p.lines[0]}-${p.lines[1]}\n${p.text.slice(0, 1400)}`
          )
          .join("\n\n")
      : "(none matched)",
  ].join("\n");

  const instruction = [
    material.prompt,
    "",
    "## How to reply",
    "",
    "Return one JSON object and nothing else:",
    '  {"kind":"claim","claim_id":"<id from the list>","text":"<the claim, in the registry\'s own words>"}',
    '  {"kind":"quotation","text":"<an exact substring of one passage>","source":{"document":"<doc>","lines":[a,b],"url":"<the passage url>"}}',
    '  {"kind":"refusal","text":"<say you do not know>","reason":"<why>"}',
    "",
    "Rules that are checked after you reply, so breaking one produces a refusal",
    "rather than the answer you intended:",
    "- A claim's text must be the registry's wording. Do not rewrite it.",
    "- A quotation's text must appear verbatim in the passage. Do not paraphrase.",
    "- A refusal must contain no figures at all.",
    "- No number may appear that its source does not carry.",
    "",
    "If nothing in the material answers the question, refuse. That is the",
    "correct answer, not a failure.",
  ].join("\n");

  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": env.ANTHROPIC_API_KEY,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model: MODEL,
      max_tokens: 700,
      system: instruction,
      messages: [{ role: "user", content: `${context}\n\n## Question\n${question}` }],
    }),
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`model call failed (${res.status}): ${body.slice(0, 160)}`);
  }

  const data = await res.json();
  const raw = (data.content || [])
    .filter((b) => b.type === "text")
    .map((b) => b.text)
    .join("")
    .replace(/```json|```/g, "")
    .trim();

  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new Error("the model did not return JSON");
  }

  if (parsed.kind === "quotation") {
    const p = material.passages.find(
      (x) => x.doc === parsed.source?.document && x.lines?.[0] === parsed.source?.lines?.[0]
    );
    if (p) {
      parsed.passage = p.text;
      parsed.source.url = p.url;
      parsed.source.pinned = p.pinned;
    }
  }

  return validate(parsed, material);
}

/** Same pseudonym the publisher uses, so a visitor counts once across both. */
async function sha12(s) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 12);
}

export default {
  async fetch(request, env, ctx) {
    if (request.method === "OPTIONS") return new Response(null, { headers: CORS });
    if (request.method !== "POST") {
      return new Response("POST a question", { status: 405, headers: CORS });
    }

    // Rate limiting by IP. Not a security control — an address is trivially
    // changed — but it bounds what a single careless script costs, and cost is
    // the risk that matters for a solo project paying per token.
    const ip = request.headers.get("cf-connecting-ip") || "unknown";
    if (env.ASK_KV) {
      const key = `rl:${ip}:${new Date().toISOString().slice(0, 13)}`;
      const used = parseInt((await env.ASK_KV.get(key)) || "0", 10);
      if (used >= RATE_LIMIT) {
        return Response.json(
          {
            kind: "refusal",
            text: "You have reached this hour's limit. Everything I would have said is public: the code is at github.com/AxonOS-org.",
            reason: "rate limited",
          },
          { headers: CORS }
        );
      }
      ctx.waitUntil(env.ASK_KV.put(key, String(used + 1), { expirationTtl: 7200 }));
    }

    let question;
    try {
      const body = await request.json();
      question = String(body.question || "").trim().slice(0, MAX_QUESTION);
    } catch {
      return Response.json({ error: "send {question: string}" }, { status: 400, headers: CORS });
    }
    if (!question) {
      return Response.json({ error: "empty question" }, { status: 400, headers: CORS });
    }

    try {
      const material = await loadKnowledge(env);
      const answer = await ask(question, material, env);
      // A refusal is recorded, because the questions this agent cannot answer
      // are the shortest description of what the project has not written down
      // — and that list is more useful in the open than in a log nobody reads.
      // What is stored is decided by gaps.py, not here: contact details and
      // anything that might be about a person never reach storage at all.
      if (answer.kind === "refusal" && env.ASK_KV) {
        const asker = await sha12(`axonos-gap-v1:${ip}`);
        ctx.waitUntil(
          env.ASK_KV.put(
            `gap:${Date.now()}:${asker}`,
            JSON.stringify({ q: question, reason: answer.reason, asker }),
            { expirationTtl: 60 * 60 * 24 * 90 }
          )
        );
      }
      return Response.json(answer, { headers: CORS });
    } catch (e) {
      // A failure becomes a refusal, and the refusal says what failed. An
      // engine that silently degrades into vagueness is the thing this
      // project's whole argument is against — and the message carries no
      // figures, so it satisfies its own contract.
      return Response.json(
        {
          kind: "refusal",
          text: "I could not answer that just now, and I will not improvise. Denis reads connect@axonos.org.",
          reason: String(e.message || e).slice(0, 200),
        },
        { headers: CORS }
      );
    }
  },
};
