// SERVER-ONLY question banks. This module imports the full question content
// (q / opts / correct answer / explanation) and must NEVER be imported by a
// client component — doing so would re-ship the whole bank to the browser,
// which is exactly the exposure this refactor closes. It is imported only by
// the server route handler src/app/api/questions/route.ts.
//
// The client gets questions per-session from that gated API, and gets category
// metadata (non-secret) from src/app/tradeCategories.js.

import { QUESTIONS_433A } from "../questions433A";
import { QUESTIONS_309A } from "../questions309A";
import { QUESTIONS_442A } from "../questions442A";
import { QUESTIONS_306A } from "../questions306A";
import { QUESTIONS_430A } from "../questions430A";
import { QUESTIONS_307A } from "../questions307A";
import { QUESTIONS_403A } from "../questions403A";
import { QUESTIONS_310S } from "../questions310S";
import { QUESTIONS_456A } from "../questions456A";

export const BANKS = {
  "433A": QUESTIONS_433A,
  "309A": QUESTIONS_309A,
  "442A": QUESTIONS_442A,
  "306A": QUESTIONS_306A,
  "430A": QUESTIONS_430A,
  "307A": QUESTIONS_307A,
  "403A": QUESTIONS_403A,
  "310S": QUESTIONS_310S,
  "456A": QUESTIONS_456A,
};

export const TRADE_IDS = Object.keys(BANKS);

export const FREE_POOL_SIZE = 20;   // public sample per trade (matches "20 free daily")
const MAX_PER_REQUEST = 400;        // hard cap on questions returned in one call

function shuffle(a) {
  const b = [...a];
  for (let i = b.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [b[i], b[j]] = [b[j], b[i]];
  }
  return b;
}

// Deterministic public sample: round-robin across categories (sorted by id) so
// the free set spans the trade rather than clustering in one block. Stable
// across requests (safe to be public / cacheable).
function buildFreePool(bank, size = FREE_POOL_SIZE) {
  const byCat = new Map();
  for (const q of [...bank].sort((a, b) => a.id - b.id)) {
    if (!byCat.has(q.cat)) byCat.set(q.cat, []);
    byCat.get(q.cat).push(q);
  }
  const lists = [...byCat.values()];
  const pool = [];
  let i = 0;
  while (pool.length < size && lists.some(l => l.length)) {
    const list = lists[i % lists.length];
    if (list.length) pool.push(list.shift());
    i++;
  }
  return pool.slice(0, size);
}

export const FREE_POOL = Object.fromEntries(
  Object.entries(BANKS).map(([id, bank]) => [id, buildFreePool(bank)])
);

// Strip nothing — the current session legitimately needs answers to grade —
// but only ever return the entitled pool, capped, for the requested mode.
export function selectQuestions({ trade, mode, cat, ids, entitled, examCount }) {
  const bank = BANKS[trade];
  if (!bank) return [];
  const pool = entitled ? bank : (FREE_POOL[trade] || []);

  let qs;
  switch (mode) {
    case "cat":
      qs = pool.filter(q => q.cat === cat);
      break;
    case "daily":
      qs = shuffle(pool).slice(0, 20);
      break;
    case "hard":
      qs = shuffle(pool.filter(q => q.type === "critical")).slice(0, 20);
      break;
    case "exam": {
      const n = Math.min(examCount || pool.length, pool.length);
      qs = shuffle(pool).slice(0, n);
      break;
    }
    case "review": {
      const wanted = new Set((ids || []).map(Number));
      qs = shuffle(pool.filter(q => wanted.has(q.id))).slice(0, 30);
      break;
    }
    case "weak":
      qs = shuffle(pool.filter(q => q.cat === cat)).slice(0, 20);
      break;
    default:
      qs = shuffle(pool);
  }

  // Free tier is always bounded to its sample pool regardless of mode.
  if (!entitled) qs = qs.slice(0, FREE_POOL_SIZE);

  return qs.slice(0, MAX_PER_REQUEST);
}
