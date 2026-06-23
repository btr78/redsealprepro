// Supabase: magic-link sign-in + cross-device progress sync.
// Fully optional — if env vars are missing, `supabase` is null and the app falls back to
// localStorage-only behaviour (no breakage). Uses ONLY the public anon key (RLS protects rows).
import { createClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const anon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

export const supabase = (typeof window !== "undefined" && url && anon)
  ? createClient(url, anon, { auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true } })
  : null;

// progress = every localStorage key the app uses for stats/streak/wrong-answers/category perf
const PROGRESS_KEY = (k) => k === "tp-stats" || k === "rsp_streak" || k.startsWith("rsp_wrong_") || k.startsWith("rsp_catperf_");

export function gatherProgress() {
  const data = {};
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k && PROGRESS_KEY(k)) data[k] = localStorage.getItem(k);
    }
  } catch {}
  return data;
}

export function applyProgress(data) {
  if (!data || typeof data !== "object") return;
  for (const [k, v] of Object.entries(data)) {
    try { if (PROGRESS_KEY(k) && typeof v === "string") localStorage.setItem(k, v); } catch {}
  }
}

export async function loadCloudProgress(userId) {
  if (!supabase || !userId) return null;
  try {
    const { data, error } = await supabase.from("progress").select("data").eq("user_id", userId).maybeSingle();
    if (error) return null;
    return data?.data || null;
  } catch { return null; }
}

export async function saveCloudProgress(userId) {
  if (!supabase || !userId) return;
  try {
    await supabase.from("progress").upsert(
      { user_id: userId, data: gatherProgress(), updated_at: new Date().toISOString() },
      { onConflict: "user_id" }
    );
  } catch {}
}
