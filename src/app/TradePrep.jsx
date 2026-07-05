"use client";
// @ts-nocheck
import { useState, useEffect, useCallback, useRef } from "react";
import { QUESTIONS_433A, CATEGORIES_433A } from "./questions433A";
import { QUESTIONS_309A, CATEGORIES_309A } from "./questions309A";
import { QUESTIONS_442A, CATEGORIES_442A } from "./questions442A";
import { QUESTIONS_306A, CATEGORIES_306A } from "./questions306A";
import { QUESTIONS_430A, CATEGORIES_430A } from "./questions430A";
import { QUESTIONS_307A, CATEGORIES_307A } from "./questions307A";
import { QUESTIONS_403A, CATEGORIES_403A } from "./questions403A";
import { QUESTIONS_310S, CATEGORIES_310S } from "./questions310S";
import { QUESTIONS_456A, CATEGORIES_456A } from "./questions456A";
import { supabase, loadCloudProgress, saveCloudProgress, applyProgress } from "./supabaseClient";

// ═══════════════════════════════════════════════════════════════
// TRADEPREP PRO — Red Seal Exam Prep SaaS
// Multi-trade • AI Tutor • Subscription • PWA-Ready
// ═══════════════════════════════════════════════════════════════

// ─── TRADE DEFINITIONS ──────────────────────────────────────
const TRADES = [
  { id: "433A", name: "Industrial Mechanic (Millwright)", icon: "⚙️", questions: 311, active: true, color: "#ff6b35" },
  { id: "309A", name: "Construction Electrician", icon: "⚡", questions: 135, active: true, color: "#3498db" },
  { id: "442A", name: "Industrial Electrician", icon: "🔌", questions: 135, active: true, color: "#9b59b6" },
  { id: "306A", name: "Plumber", icon: "🔧", questions: 135, active: true, color: "#1abc9c" },
  { id: "430A", name: "Tool and Die Maker", icon: "🔩", questions: 135, active: true, color: "#f39c12" },
  { id: "403A", name: "Carpenter", icon: "🪚", questions: 100, active: true, color: "#e67e22" },
  { id: "310S", name: "Auto Service Technician", icon: "🚗", questions: 120, active: true, color: "#e74c3c" },
  { id: "307A", name: "Steamfitter/Pipefitter", icon: "🔩", questions: 130, active: true, color: "#2ecc71" },
  { id: "456A", name: "Welder", icon: "🔥", questions: 120, active: true, color: "#f39c12" },
];

// ─── UTILITIES ──────────────────────────────────────────────
const shuffle = (a) => { const b=[...a]; for(let i=b.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[b[i],b[j]]=[b[j],b[i]];} return b; };
// Randomize each question's answer positions (banks were authored with the correct option
// almost always in slot B). Shuffle by index so duplicate option text can't break the remap.
const shuffleOpts = (q) => { const order = shuffle(q.opts.map((_, i) => i)); return { ...q, opts: order.map(i => q.opts[i]), ans: order.indexOf(q.ans) }; };
const hexRgb = (h) => { const r=parseInt(h.slice(1,3),16),g=parseInt(h.slice(3,5),16),b=parseInt(h.slice(5,7),16); return `${r},${g},${b}`; };
const fmtTime = (s) => `${Math.floor(s/60)}:${(s%60).toString().padStart(2,"0")}`;

// ─── STYLES ─────────────────────────────────────────────────
const T = {
  bg: "#07090f",
  bg2: "#0d1117",
  bg3: "#161b22",
  surface: "rgba(255,255,255,0.03)",
  border: "rgba(255,255,255,0.08)",
  text: "#e6edf3",
  text2: "#8b949e",
  accent: "#ff6b35",
  accent2: "#ffa726",
  green: "#2ea043",
  red: "#f85149",
  font: "'DM Sans', 'Segoe UI', system-ui, sans-serif",
  mono: "'JetBrains Mono', 'Fira Code', monospace",
  radius: 12,
};

// ─── MAIN APP ───────────────────────────────────────────────
export default function TradePrep() {
  const [page, setPage] = useState("landing");
  // Optimistic: treat stored token as subscribed until server says otherwise
  const [sub, setSub] = useState(() => {
    if (typeof window === "undefined") return false;
    return !!localStorage.getItem("rsp_token");
  });
  const [trade, setTrade] = useState(null);
  const [showActivate, setShowActivate]     = useState(false);
  const [activateEmail, setActivateEmail]   = useState("");
  const [activateLoading, setActivateLoading] = useState(false);
  const [activateError, setActivateError]   = useState("");
  const [activateSent, setActivateSent]     = useState(false);
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  // Annual plan appears once NEXT_PUBLIC_ANNUAL_PRICE (+ STRIPE_PRICE_ID_ANNUAL) is configured
  const ANNUAL_PRICE = process.env.NEXT_PUBLIC_ANNUAL_PRICE;
  const [plan, setPlan] = useState("monthly");
  const [showWrong, setShowWrong] = useState(false);
  const [quiz, setQuiz] = useState(null); // { questions, idx, selected, answered, score, answers, timer }
  const [chat, setChat] = useState({ open: false, messages: [], input: "", loading: false });
  const [stats, setStats] = useState({ sessions: 0, attempted: 0, correct: 0, best: 0 });
  const [hovered, setHovered] = useState(null);
  // ─── ACCOUNTS (Supabase magic-link + cross-device progress) ───
  const [authUser, setAuthUser]   = useState(null);
  const [authEmail, setAuthEmail] = useState("");
  const [authSent, setAuthSent]   = useState(false);
  const [authBusy, setAuthBusy]   = useState(false);
  const [showSignIn, setShowSignIn] = useState(false);
  const [authErr, setAuthErr]     = useState("");

  // ─── SPACED REPETITION & STREAK ───────────────────────────
  const [wrongBank, setWrongBank] = useState(() => {
    if (typeof window === "undefined") return {};
    try { return JSON.parse(localStorage.getItem("rsp_wrong_" + (trade?.id || "")) || "{}"); } catch { return {}; }
  });
  const [streak, setStreak] = useState(() => {
    if (typeof window === "undefined") return { days: 0, last: "" };
    try { return JSON.parse(localStorage.getItem("rsp_streak") || '{"days":0,"last":""}'); } catch { return { days: 0, last: "" }; }
  });
  const updateStreak = () => {
    const today = new Date().toISOString().slice(0, 10);
    setStreak(s => {
      if (s.last === today) return s;
      const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
      const ns = { days: s.last === yesterday ? s.days + 1 : 1, last: today };
      localStorage.setItem("rsp_streak", JSON.stringify(ns));
      return ns;
    });
  };
  const saveWrong = (tradeId, answers, questions) => {
    const bank = JSON.parse(localStorage.getItem("rsp_wrong_" + tradeId) || "{}");
    answers.filter(a => !a.ok).forEach(a => {
      bank[a.qId] = (bank[a.qId] || 0) + 1;
    });
    // Remove questions answered correctly
    answers.filter(a => a.ok).forEach(a => {
      if (bank[a.qId]) { bank[a.qId]--; if (bank[a.qId] <= 0) delete bank[a.qId]; }
    });
    localStorage.setItem("rsp_wrong_" + tradeId, JSON.stringify(bank));
    setWrongBank(bank);
  };
  const getWeakCats = () => {
    const allQs = getQuestions();
    const cats = getCategories();
    const key = "rsp_catperf_" + (trade?.id || "");
    try { 
      const perf = JSON.parse(localStorage.getItem(key) || "{}");
      return cats.map(c => ({
        ...c, pct: perf[c.id] ? Math.round((perf[c.id].ok / perf[c.id].total) * 100) : -1,
        total: perf[c.id]?.total || 0, ok: perf[c.id]?.ok || 0
      })).filter(c => c.total > 0).sort((a, b) => a.pct - b.pct);
    } catch { return []; }
  };
  const saveCatPerf = (tradeId, answers, questions) => {
    const key = "rsp_catperf_" + tradeId;
    const perf = JSON.parse(localStorage.getItem(key) || "{}");
    answers.forEach(a => {
      const q = questions.find(qq => qq.id === a.qId);
      if (!q) return;
      if (!perf[q.cat]) perf[q.cat] = { ok: 0, total: 0 };
      perf[q.cat].total++;
      if (a.ok) perf[q.cat].ok++;
    });
    localStorage.setItem(key, JSON.stringify(perf));
  };
  const timerRef = useRef(null);
  const chatEndRef = useRef(null);

  // Load stats + verify subscription server-side
  useEffect(() => {
    (async () => {
      try {
        const raw = localStorage.getItem("tp-stats");
        if (raw) setStats(JSON.parse(raw));
      } catch(e) {}

      // Stripe success redirect → auto-activate from the checkout session,
      // falling back to the email-verification modal if that fails
      if (typeof window !== "undefined") {
        const params = new URLSearchParams(window.location.search);
        if (params.get("sub") === "success") {
          const checkoutSessionId = params.get("session_id");
          window.history.replaceState({}, "", window.location.pathname);
          if (checkoutSessionId) {
            try {
              const res = await fetch("/api/verify-subscription", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ checkoutSessionId }),
              });
              const data = await res.json();
              if (data.subscribed && data.token) {
                localStorage.setItem("rsp_token", data.token);
                setSub(true);
                return;
              }
            } catch {}
          }
          setSub(false);
          localStorage.removeItem("rsp_token");
          setShowActivate(true);
          return;
        }
      }

      // Verify stored token against server
      const token = localStorage.getItem("rsp_token");
      if (token) {
        try {
          const res = await fetch("/api/verify-subscription", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ token }),
          });
          const data = await res.json();
          if (data.subscribed) {
            setSub(true);
            if (data.token) localStorage.setItem("rsp_token", data.token);
          } else {
            setSub(false);
            localStorage.removeItem("rsp_token");
          }
        } catch {
          // Network error — keep optimistic state, will re-check next load
        }
      }
    })();
  }, []);

  // Verify the signed-in Supabase session against Stripe; the server extracts
  // the email from the session token, so ownership of the address is proven.
  const verifySession = async () => {
    if (!supabase) return { subscribed: false };
    const { data } = await supabase.auth.getSession();
    const supabaseToken = data?.session?.access_token;
    if (!supabaseToken) return { subscribed: false };
    const res = await fetch("/api/verify-subscription", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ supabaseToken }),
    });
    return res.json();
  };

  // ─── Supabase auth + cross-device progress hydration ───
  useEffect(() => {
    if (!supabase) return;
    const hydrate = async (user) => {
      setAuthUser(user || null);
      if (!user) return;
      // Signed in with no access token → check Stripe for a subscription under
      // this (ownership-proven) email. Restores Pro on any device they sign into.
      if (!localStorage.getItem("rsp_token")) {
        const pending = localStorage.getItem("rsp_activate_pending");
        localStorage.removeItem("rsp_activate_pending");
        try {
          const data = await verifySession();
          if (data.subscribed && data.token) {
            localStorage.setItem("rsp_token", data.token);
            setSub(true);
            setShowActivate(false);
            setActivateSent(false);
          } else if (pending) {
            // They came back from an activation magic link but have no subscription
            setActivateSent(false);
            setShowActivate(true);
            setActivateError(`No active subscription found for ${user.email}. Retry with the email used at checkout, or contact support@redsealprep.pro`);
          }
        } catch {}
      }
      const cloud = await loadCloudProgress(user.id);
      if (cloud && Object.keys(cloud).length) {
        applyProgress(cloud);                       // pull their saved progress onto this device
        try { const s = localStorage.getItem("tp-stats"); if (s) setStats(JSON.parse(s)); } catch {}
        try { const st = localStorage.getItem("rsp_streak"); if (st) setStreak(JSON.parse(st)); } catch {}
        try { setWrongBank(JSON.parse(localStorage.getItem("rsp_wrong_" + (trade?.id || "")) || "{}")); } catch {}
      } else {
        saveCloudProgress(user.id);                 // first sign-in: push whatever's already local
      }
    };
    supabase.auth.getSession().then(({ data }) => hydrate(data?.session?.user));
    const { data } = supabase.auth.onAuthStateChange((_e, session) => { setShowSignIn(false); setAuthSent(false); hydrate(session?.user); });
    return () => data?.subscription?.unsubscribe();
  }, []);

  const sendMagicLink = async () => {
    if (!supabase) { setAuthErr("Sign-in isn't enabled yet."); return; }
    if (!authEmail.includes("@")) { setAuthErr("Enter a valid email."); return; }
    setAuthBusy(true); setAuthErr("");
    try {
      const { error } = await supabase.auth.signInWithOtp({ email: authEmail.trim(), options: { emailRedirectTo: typeof window !== "undefined" ? window.location.origin : undefined } });
      if (error) setAuthErr(error.message); else setAuthSent(true);
    } catch { setAuthErr("Couldn't send the link — try again."); }
    finally { setAuthBusy(false); }
  };
  const signOut = async () => { try { await supabase?.auth.signOut(); } catch {} setAuthUser(null); };
  const syncCloud = () => { if (authUser && supabase) saveCloudProgress(authUser.id); };

  const saveStats = async (s) => { try { localStorage.setItem("tp-stats", JSON.stringify(s)); } catch(e) {} };

  const activateSubscription = async () => {
    setActivateLoading(true);
    setActivateError("");
    try {
      // Already signed in — verify that email against Stripe directly
      if (authUser && supabase) {
        const data = await verifySession();
        if (data.subscribed && data.token) {
          localStorage.setItem("rsp_token", data.token);
          setSub(true);
          setShowActivate(false);
        } else {
          setActivateError(`No active subscription found for ${authUser.email}. Sign out and retry with the email used at checkout, or contact support@redsealprep.pro`);
        }
        return;
      }
      // Not signed in — email them a magic link to prove they own the address
      if (!activateEmail.includes("@")) { setActivateError("Enter the email you used at checkout."); return; }
      if (!supabase) { setActivateError("Verification is temporarily unavailable — contact support@redsealprep.pro"); return; }
      localStorage.setItem("rsp_activate_pending", "1");
      const { error } = await supabase.auth.signInWithOtp({
        email: activateEmail.trim().toLowerCase(),
        options: { emailRedirectTo: window.location.origin },
      });
      if (error) setActivateError(error.message);
      else setActivateSent(true);
    } catch {
      setActivateError("Connection error. Please try again.");
    } finally {
      setActivateLoading(false);
    }
  };

  // Timer
  useEffect(() => {
    if (quiz?.running) {
      timerRef.current = setInterval(() => setQuiz(q => {
        if (!q) return q;
        const updated = {...q, timer: q.timer+1};
        // Countdown for exam mode: auto-end when time runs out
        if (q.countdown > 0) {
          const remaining = q.countdown - q.timer - 1;
          if (remaining <= 0) {
            clearInterval(timerRef.current);
            return {...updated, running: false};
          }
        }
        return updated;
      }), 1000);
    }
    return () => clearInterval(timerRef.current);
  }, [quiz?.running]);

  // Scroll chat
  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [chat.messages]);

  // ─── TRADE-AWARE HELPERS ────────────────────────────────────
  const getQuestions = () => {
    if (trade?.id === "309A") return QUESTIONS_309A;
    if (trade?.id === "442A") return QUESTIONS_442A;
    if (trade?.id === "306A") return QUESTIONS_306A;
    if (trade?.id === "430A") return QUESTIONS_430A;
    if (trade?.id === "307A") return QUESTIONS_307A;
    if (trade?.id === "403A") return QUESTIONS_403A;
    if (trade?.id === "310S") return QUESTIONS_310S;
    if (trade?.id === "456A") return QUESTIONS_456A;
    return QUESTIONS_433A;
  };
  const getCategories = () => {
    if (trade?.id === "309A") return CATEGORIES_309A;
    if (trade?.id === "442A") return CATEGORIES_442A;
    if (trade?.id === "306A") return CATEGORIES_306A;
    if (trade?.id === "430A") return CATEGORIES_430A;
    if (trade?.id === "307A") return CATEGORIES_307A;
    if (trade?.id === "403A") return CATEGORIES_403A;
    if (trade?.id === "310S") return CATEGORIES_310S;
    if (trade?.id === "456A") return CATEGORIES_456A;
    return CATEGORIES_433A;
  };

  // ─── QUIZ LOGIC ───────────────────────────────────────────
  const startQuiz = (mode, cat) => {
    const allQs = getQuestions();
    let qs = allQs;
    let countdown = 0;

    if (mode === "cat") qs = qs.filter(q => q.cat === cat);
    else if (mode === "daily") qs = shuffle(qs).slice(0, 20);
    else if (mode === "hard") qs = shuffle(qs.filter(q => q.type === "critical")).slice(0, 20);
    else if (mode === "exam") {
      // Real exam simulator: exact question count per trade, 4hr timer
      const examCount = trade?.questions || 120;
      qs = shuffle(allQs).slice(0, Math.min(examCount, allQs.length));
      countdown = 4 * 60 * 60; // 4 hours in seconds
    }
    else if (mode === "review") {
      // Spaced repetition: pull questions from wrong bank
      const bank = JSON.parse(localStorage.getItem("rsp_wrong_" + (trade?.id || "")) || "{}");
      const wrongIds = Object.keys(bank).map(Number);
      qs = allQs.filter(q => wrongIds.includes(q.id));
      if (qs.length === 0) { alert("No wrong answers to review! Keep practicing."); return; }
      qs = shuffle(qs).slice(0, Math.min(30, qs.length));
    }
    else if (mode === "weak") {
      // Weakest category drill
      const weak = getWeakCats();
      if (weak.length === 0) { alert("Complete some sessions first to identify weak spots."); return; }
      const weakestCat = weak[0].id;
      qs = shuffle(allQs.filter(q => q.cat === weakestCat)).slice(0, 20);
    }
    else qs = shuffle(qs);

    if (!sub && !["daily"].includes(mode)) {
      qs = shuffle(allQs).slice(0, 20);
    }

    // Free tier: one 20-question session per day (any trade), as advertised
    if (!sub) {
      const today = new Date().toISOString().slice(0, 10);
      if (localStorage.getItem("rsp_free_day") === today) {
        alert("That's your free 20 questions done for today — come back tomorrow, or go Pro for unlimited practice, every mode, and the AI tutor.");
        setPage("landing");
        return;
      }
      try { localStorage.setItem("rsp_free_day", today); } catch {}
    }

    updateStreak();
    setQuiz({ questions: shuffle(qs).map(shuffleOpts), idx: 0, selected: null, answered: false, score: 0, answers: [], timer: 0, running: true, mode, countdown });
    setPage("quiz");
  };

  const selectAnswer = (i) => {
    if (quiz.answered) return;
    const correct = i === quiz.questions[quiz.idx].ans;
    setQuiz(q => ({
      ...q, selected: i, answered: true,
      score: correct ? q.score + 1 : q.score,
      answers: [...q.answers, { qId: q.questions[q.idx].id, sel: i, ok: correct }]
    }));
  };

  const nextQ = () => {
    if (quiz.idx < quiz.questions.length - 1) {
      setQuiz(q => ({ ...q, idx: q.idx + 1, selected: null, answered: false }));
    } else {
      const newStats = {
        sessions: stats.sessions + 1,
        attempted: stats.attempted + quiz.questions.length,
        correct: stats.correct + quiz.score,
        best: Math.max(stats.best, Math.round((quiz.score / quiz.questions.length) * 100))
      };
      setStats(newStats);
      saveStats(newStats);
      // Save wrong answers for spaced repetition + category performance
      const finalAnswers = [...quiz.answers, { qId: quiz.questions[quiz.idx].id, sel: quiz.selected, ok: quiz.selected === quiz.questions[quiz.idx].ans }];
      saveWrong(trade?.id, finalAnswers, quiz.questions);
      saveCatPerf(trade?.id, finalAnswers, quiz.questions);
      syncCloud();   // push this session's progress to the signed-in account (if any)
      setQuiz(q => ({ ...q, running: false }));
      setPage("results");
    }
  };

  // ─── AI TUTOR ─────────────────────────────────────────────
  const sendChat = async () => {
    if (!chat.input.trim() || chat.loading) return;
    const userMsg = chat.input.trim();
    const newMsgs = [...chat.messages, { role: "user", text: userMsg }];
    setChat(c => ({ ...c, messages: newMsgs, input: "", loading: true }));

    try {
      const contextQ = quiz?.questions?.[quiz.idx];
      const questionContext = contextQ ? { question: contextQ.q, options: contextQ.opts, correct: contextQ.opts[contextQ.ans], explanation: contextQ.exp, category: contextQ.cat } : null;

      const resp = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: newMsgs,
          questionContext,
          token: typeof window !== "undefined" ? localStorage.getItem("rsp_token") : null,
          trade: trade ? { id: trade.id, name: trade.name } : null,
        })
      });
      if (resp.status === 401) {
        setChat(c => ({ ...c, messages: [...c.messages, { role: "ai", text: "🔒 AI Tutor is a Pro feature. Subscribe to unlock unlimited tutoring." }], loading: false }));
        return;
      }
      const data = await resp.json();
      const aiText = data.text || "I couldn't process that. Try again.";
      setChat(c => ({ ...c, messages: [...c.messages, { role: "ai", text: aiText }], loading: false }));
    } catch (e) {
      setChat(c => ({ ...c, messages: [...c.messages, { role: "ai", text: "Connection issue. Check your network and try again." }], loading: false }));
    }
  };

  // ─── SHARED STYLES ────────────────────────────────────────
  const btn = (primary) => ({
    background: primary ? `linear-gradient(135deg, ${T.accent}, #e65100)` : T.surface,
    border: primary ? "none" : `1px solid ${T.border}`,
    borderRadius: T.radius, padding: "14px 24px", color: T.text,
    fontSize: 15, fontWeight: 700, cursor: "pointer", fontFamily: T.font,
    letterSpacing: "0.3px", transition: "all 0.2s", width: "100%", boxSizing: "border-box"
  });

  const wrap = { maxWidth: 800, margin: "0 auto", padding: "16px" };

  // ═══════════════════════════════════════════════════════════
  // Sign-in modal — shared across pages (landing header + results nudge)
  const signInModal = showSignIn && (
    <div onClick={() => setShowSignIn(false)} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.88)", zIndex: 999, display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}>
      <div onClick={e => e.stopPropagation()} style={{ background: T.bg2, border: `1px solid ${T.border}`, borderRadius: 20, padding: "36px 32px", maxWidth: 420, width: "100%" }}>
        {authSent ? (
          <>
            <div style={{ fontSize: 40, textAlign: "center", marginBottom: 10 }}>✉️</div>
            <h2 style={{ textAlign: "center", fontSize: 22, fontWeight: 900, marginBottom: 8, letterSpacing: "-0.5px" }}>Check your email</h2>
            <p style={{ textAlign: "center", color: T.text2, fontSize: 14, marginBottom: 24, lineHeight: 1.6 }}>
              We sent a sign-in link to <b style={{ color: T.text }}>{authEmail}</b>. Click it to log in — your progress will then sync across all your devices.
            </p>
            <button onClick={() => setShowSignIn(false)} style={{ ...btn(true) }}>Done</button>
          </>
        ) : (
          <>
            <div style={{ fontSize: 40, textAlign: "center", marginBottom: 10 }}>☁️</div>
            <h2 style={{ textAlign: "center", fontSize: 22, fontWeight: 900, marginBottom: 8, letterSpacing: "-0.5px" }}>Save your progress</h2>
            <p style={{ textAlign: "center", color: T.text2, fontSize: 14, marginBottom: 28, lineHeight: 1.6 }}>
              Sign in to keep your scores, streak, and weak spots — and pick up right where you left off on any device. No password; we just email you a link.
            </p>
            <input
              type="email" value={authEmail} autoFocus
              onChange={e => { setAuthEmail(e.target.value); setAuthErr(""); }}
              onKeyDown={e => e.key === "Enter" && sendMagicLink()}
              placeholder="your@email.com"
              style={{ width: "100%", background: T.surface, border: `1px solid ${authErr ? T.red : T.border}`, borderRadius: 10, padding: "14px 16px", color: T.text, fontSize: 15, fontFamily: T.font, outline: "none", boxSizing: "border-box", marginBottom: authErr ? 8 : 16 }}
            />
            {authErr && <p style={{ color: T.red, fontSize: 12, marginBottom: 16, lineHeight: 1.5 }}>{authErr}</p>}
            <button onClick={sendMagicLink} disabled={authBusy} style={{ ...btn(true), opacity: authBusy ? 0.7 : 1 }}>
              {authBusy ? "Sending..." : "Email me a sign-in link →"}
            </button>
          </>
        )}
      </div>
    </div>
  );

  // LANDING PAGE
  // ═══════════════════════════════════════════════════════════
  if (page === "landing") return (
    <div style={{ fontFamily: T.font, background: T.bg, minHeight: "100vh", color: T.text }}>
      {/* NAV */}
      <div style={{ padding: "16px 20px", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: `1px solid ${T.border}`, position: "sticky", top: 0, background: "rgba(7,9,15,0.92)", backdropFilter: "blur(20px)", zIndex: 100 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{ width: 32, height: 32, background: `linear-gradient(135deg, ${T.accent}, #e65100)`, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16 }}>⚙️</div>
          <span style={{ fontWeight: 800, fontSize: 16, letterSpacing: "-0.3px" }}>RedSeal<span style={{ color: T.accent }}>Prep</span></span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {supabase && (authUser
            ? <button onClick={signOut} style={{ background: "transparent", border: `1px solid ${T.border}`, color: T.text2, borderRadius: 8, padding: "9px 12px", fontSize: 12, cursor: "pointer", fontWeight: 600 }}>✓ {(authUser.email||"").split("@")[0]} · Sign out</button>
            : <button onClick={() => { setShowSignIn(true); setAuthSent(false); setAuthErr(""); }} style={{ background: "transparent", border: `1px solid ${T.border}`, color: T.text, borderRadius: 8, padding: "9px 14px", fontSize: 13, cursor: "pointer", fontWeight: 600 }}>Sign in</button>)}
          <button onClick={() => setPage("trades")} style={{ ...btn(true), width: "auto", padding: "10px 20px", fontSize: 13 }}>Start Free →</button>
        </div>
      </div>

      {/* HERO */}
      <div style={{ ...wrap, textAlign: "center", padding: "60px 20px 40px" }}>
        <div style={{ display: "inline-block", background: "rgba(255,107,53,0.1)", border: `1px solid rgba(255,107,53,0.25)`, borderRadius: 20, padding: "6px 16px", fontSize: 12, color: T.accent, fontWeight: 600, marginBottom: 20, letterSpacing: "1px" }}>
          🇨🇦 CANADA'S #1 RED SEAL EXAM PREP
        </div>
        <h1 style={{ fontSize: "clamp(2rem, 6vw, 3.5rem)", fontWeight: 900, lineHeight: 1.1, marginBottom: 16, letterSpacing: "-1px" }}>
          Practice Tests for Your <span style={{ background: `linear-gradient(135deg, ${T.accent}, ${T.accent2})`, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>Red Seal</span> Exam<br/>to Help You Pass
        </h1>
        <p style={{ fontSize: "clamp(1rem, 2.5vw, 1.2rem)", color: T.text2, maxWidth: 520, margin: "0 auto 32px", lineHeight: 1.6 }}>
          1,320+ practice questions across 9 trades with AI-powered tutoring. Built by tradespeople, for tradespeople.
        </p>
        <div style={{ display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap" }}>
          <button onClick={() => setPage("trades")} style={{ ...btn(true), width: "auto", padding: "16px 32px", fontSize: 16 }}>Start Free Trial →</button>
        </div>
        <div style={{ display: "flex", gap: 24, justifyContent: "center", marginTop: 32, flexWrap: "wrap" }}>
          {[["1,320+", "Questions"], ["9", "Trades Live"], ["70%", "Pass Mark"], ["AI", "Tutor"]].map(([n, l]) => (
            <div key={l} style={{ textAlign: "center" }}>
              <div style={{ fontSize: 24, fontWeight: 900, color: T.accent }}>{n}</div>
              <div style={{ fontSize: 11, color: T.text2, textTransform: "uppercase", letterSpacing: "1px" }}>{l}</div>
            </div>
          ))}
        </div>
      </div>

      {/* FEATURES */}
      <div style={{ ...wrap, padding: "40px 20px" }}>
        <h2 style={{ textAlign: "center", fontSize: "clamp(1.4rem, 4vw, 2rem)", fontWeight: 800, marginBottom: 32 }}>Everything You Need to Pass</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
          {[
            { icon: "🧠", title: "AI Tutor", desc: "Ask any question and get instant expert explanations powered by AI" },
            { icon: "📊", title: "Progress Tracking", desc: "Track your accuracy by category to focus on weak areas" },
            { icon: "⚡", title: "Daily Practice", desc: "20-question daily quizzes keep you sharp over months of prep" },
            { icon: "🎯", title: "Exam-Matched", desc: "Questions follow the exact Red Seal NOA breakdown" },
            { icon: "📱", title: "Works Everywhere", desc: "Phone, tablet, laptop — study on break, at home, anywhere" },
            { icon: "🔧", title: "9 Trades Live", desc: "Millwright, Electrician, Plumber, Welder, Carpenter, Auto Tech & more — all included" },
          ].map(f => (
            <div key={f.title} style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: T.radius, padding: 20 }}>
              <div style={{ fontSize: 28, marginBottom: 8 }}>{f.icon}</div>
              <div style={{ fontWeight: 700, marginBottom: 4, fontSize: 15 }}>{f.title}</div>
              <div style={{ fontSize: 13, color: T.text2, lineHeight: 1.5 }}>{f.desc}</div>
            </div>
          ))}
        </div>
      </div>

      {/* PRICING */}
      <div style={{ ...wrap, padding: "40px 20px" }} id="pricing">
        <h2 style={{ textAlign: "center", fontSize: "clamp(1.4rem, 4vw, 2rem)", fontWeight: 800, marginBottom: 8 }}>Simple Pricing</h2>
        <p style={{ textAlign: "center", color: T.text2, marginBottom: 32, fontSize: 14 }}>Less than the cost of one failed exam attempt</p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 16 }}>
          {/* Free */}
          <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 16, padding: 28 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: T.text2, textTransform: "uppercase", letterSpacing: "2px", marginBottom: 8 }}>Free</div>
            <div style={{ fontSize: 36, fontWeight: 900, marginBottom: 4 }}>$0</div>
            <div style={{ fontSize: 13, color: T.text2, marginBottom: 20 }}>Try before you buy</div>
            {["20 free questions daily", "All 9 trades", "Score & streak tracking"].map(f => (
              <div key={f} style={{ fontSize: 13, color: T.text2, padding: "6px 0", display: "flex", gap: 8, alignItems: "center" }}>
                <span style={{ color: T.green }}>✓</span> {f}
              </div>
            ))}
            <button onClick={() => setPage("trades")} style={{ ...btn(false), marginTop: 20 }}>Get Started</button>
          </div>
          {/* Pro */}
          <div style={{ background: `linear-gradient(135deg, rgba(255,107,53,0.08), rgba(255,167,38,0.04))`, border: `2px solid ${T.accent}`, borderRadius: 16, padding: 28, position: "relative" }}>
            <div style={{ position: "absolute", top: -12, right: 20, background: T.accent, color: "white", fontSize: 11, fontWeight: 800, padding: "4px 12px", borderRadius: 12 }}>MOST POPULAR</div>
            <div style={{ fontSize: 13, fontWeight: 700, color: T.accent, textTransform: "uppercase", letterSpacing: "2px", marginBottom: 8 }}>Pro</div>
            {ANNUAL_PRICE && (
              <div style={{ display: "inline-flex", background: T.surface, border: `1px solid ${T.border}`, borderRadius: 8, padding: 3, marginBottom: 10 }}>
                {[["monthly", "Monthly"], ["annual", `Annual · save ${Math.round((1 - Number(ANNUAL_PRICE) / 144) * 100)}%`]].map(([p, label]) => (
                  <button key={p} onClick={() => setPlan(p)} style={{ background: plan === p ? T.accent : "transparent", color: plan === p ? "#fff" : T.text2, border: "none", borderRadius: 6, padding: "6px 12px", fontSize: 12, fontWeight: 700, cursor: "pointer", fontFamily: T.font }}>
                    {label}
                  </button>
                ))}
              </div>
            )}
            {plan === "annual" && ANNUAL_PRICE
              ? <div style={{ fontSize: 36, fontWeight: 900, marginBottom: 4 }}>${ANNUAL_PRICE}<span style={{ fontSize: 16, color: T.text2 }}>/yr</span></div>
              : <div style={{ fontSize: 36, fontWeight: 900, marginBottom: 4 }}>$12<span style={{ fontSize: 16, color: T.text2 }}>/mo</span></div>}
            <div style={{ fontSize: 13, color: T.text2, marginBottom: 20 }}>Everything you need to prepare</div>
            {["All 135+ questions per trade", "Full exam simulation (timed)", "AI Tutor — unlimited questions", "Category deep-dive mode", "Hard mode (critical thinking)", "Progress analytics", "All trades included", "New questions added monthly"].map(f => (
              <div key={f} style={{ fontSize: 13, color: T.text, padding: "6px 0", display: "flex", gap: 8, alignItems: "center" }}>
                <span style={{ color: T.accent }}>✓</span> {f}
              </div>
            ))}
            <button onClick={async () => {
              if (checkoutLoading) return;
              setCheckoutLoading(true);
              try {
                const res = await fetch("/api/stripe/checkout", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ plan })
                });
                const data = await res.json();
                if (data.url) window.location.href = data.url;
                else alert("Payment setup error. Please try again.");
              } catch (e) { alert("Connection error. Please try again."); }
              finally { setCheckoutLoading(false); }
            }} disabled={checkoutLoading} style={{ ...btn(true), marginTop: 20, opacity: checkoutLoading ? 0.7 : 1 }}>
              {checkoutLoading ? "Loading..." : "Start 7-Day Free Trial →"}
            </button>
            <p style={{ textAlign: "center", marginTop: 12, fontSize: 12, color: T.text2 }}>
              Already subscribed?{" "}
              <span onClick={() => setShowActivate(true)} style={{ color: T.accent, cursor: "pointer", textDecoration: "underline" }}>
                Restore access →
              </span>
            </p>
          </div>
        </div>
      </div>

      {/* TRADES PREVIEW */}
      <div style={{ ...wrap, padding: "40px 20px 60px" }}>
        <h2 style={{ textAlign: "center", fontSize: "clamp(1.2rem, 3vw, 1.6rem)", fontWeight: 800, marginBottom: 20 }}>Trades Available</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 8 }}>
          {TRADES.map(t => (
            <div key={t.id} style={{ background: T.surface, border: `1px solid ${t.active ? `rgba(${hexRgb(t.color)},0.3)` : T.border}`, borderRadius: 10, padding: "12px", textAlign: "center", opacity: t.active ? 1 : 0.5 }}>
              <div style={{ fontSize: 24 }}>{t.icon}</div>
              <div style={{ fontSize: 12, fontWeight: 700, marginTop: 4 }}>{t.id}</div>
              <div style={{ fontSize: 10, color: T.text2, marginTop: 2 }}>{t.active ? `${t.questions}Q Ready` : "Coming Soon"}</div>
            </div>
          ))}
        </div>
      </div>

      {/* DISCLAIMER FOOTER */}
      <div style={{ borderTop: `1px solid ${T.border}`, padding: "30px 20px", textAlign: "center" }}>
        <div style={{ maxWidth: 680, margin: "0 auto" }}>
          <p style={{ fontSize: 11, color: T.text2, lineHeight: 1.7, marginBottom: 12 }}>
            RedSeal Prep is an independent study tool and is not affiliated with, endorsed by, or sponsored by the Canadian Council of Directors of Apprenticeship (CCDA), the Red Seal Program, or any provincial/territorial apprenticeship authority. &quot;Red Seal&quot; refers to the Interprovincial Standards Red Seal Program. All practice questions are original content created for exam preparation purposes.
          </p>
          <p style={{ fontSize: 10, color: "rgba(139,148,158,0.5)" }}>
            © {new Date().getFullYear()} RedSeal Prep. All rights reserved. &nbsp;|&nbsp;
            <a href="/terms" target="_blank" rel="noopener noreferrer" style={{ color: "rgba(139,148,158,0.5)", textDecoration: "none", cursor: "pointer" }}> Terms</a> &nbsp;|&nbsp;
            <a href="/privacy" target="_blank" rel="noopener noreferrer" style={{ color: "rgba(139,148,158,0.5)", textDecoration: "none", cursor: "pointer" }}>Privacy</a>
          </p>
        </div>
      </div>

      {/* ACTIVATION MODAL */}
      {showActivate && (
        <div onClick={() => setShowActivate(false)} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.88)", zIndex: 999, display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}>
          <div onClick={e => e.stopPropagation()} style={{ background: T.bg2, border: `1px solid ${T.border}`, borderRadius: 20, padding: "36px 32px", maxWidth: 420, width: "100%" }}>
            {activateSent ? (
              <>
                <div style={{ fontSize: 40, textAlign: "center", marginBottom: 10 }}>✉️</div>
                <h2 style={{ textAlign: "center", fontSize: 22, fontWeight: 900, marginBottom: 8, letterSpacing: "-0.5px" }}>Check your email</h2>
                <p style={{ textAlign: "center", color: T.text2, fontSize: 14, marginBottom: 24, lineHeight: 1.6 }}>
                  We sent a secure verification link to <b style={{ color: T.text }}>{activateEmail}</b>. Click it and your Pro access unlocks automatically — on whichever device you open it.
                </p>
                <button onClick={() => setShowActivate(false)} style={{ ...btn(true) }}>Done</button>
              </>
            ) : (
              <>
                <div style={{ fontSize: 40, textAlign: "center", marginBottom: 10 }}>🎉</div>
                <h2 style={{ textAlign: "center", fontSize: 22, fontWeight: 900, marginBottom: 8, letterSpacing: "-0.5px" }}>Activate Your Pro Access</h2>
                <p style={{ textAlign: "center", color: T.text2, fontSize: 14, marginBottom: 28, lineHeight: 1.6 }}>
                  {authUser
                    ? <>You&apos;re signed in as <b style={{ color: T.text }}>{authUser.email}</b>. We&apos;ll check for a subscription under this email.</>
                    : <>Enter the email you used at checkout. We&apos;ll send you a secure link to verify it&apos;s you and unlock full access.</>}
                </p>
                {!authUser && (
                  <input
                    type="email"
                    value={activateEmail}
                    onChange={e => { setActivateEmail(e.target.value); setActivateError(""); }}
                    onKeyDown={e => e.key === "Enter" && activateSubscription()}
                    placeholder="your@email.com"
                    autoFocus
                    style={{
                      width: "100%", background: T.surface,
                      border: `1px solid ${activateError ? T.red : T.border}`,
                      borderRadius: 10, padding: "14px 16px", color: T.text,
                      fontSize: 15, fontFamily: T.font, outline: "none",
                      boxSizing: "border-box", marginBottom: activateError ? 8 : 16,
                    }}
                  />
                )}
                {activateError && (
                  <p style={{ color: T.red, fontSize: 12, marginBottom: 16, lineHeight: 1.5 }}>{activateError}</p>
                )}
                <button
                  onClick={activateSubscription}
                  disabled={activateLoading}
                  style={{ ...btn(true), opacity: activateLoading ? 0.7 : 1 }}
                >
                  {activateLoading ? "Verifying..." : authUser ? "Verify My Subscription →" : "Email Me a Verification Link →"}
                </button>
                <p style={{ textAlign: "center", color: T.text2, fontSize: 12, marginTop: 16 }}>
                  Issues? Email{" "}
                  <a href="mailto:support@redsealprep.pro" style={{ color: T.accent }}>support@redsealprep.pro</a>
                </p>
              </>
            )}
          </div>
        </div>
      )}

      {/* SIGN-IN MODAL — Supabase magic link */}
      {signInModal}
    </div>
  );

  // ═══════════════════════════════════════════════════════════
  // TRADE SELECTION
  // ═══════════════════════════════════════════════════════════
  if (page === "trades") return (
    <div style={{ fontFamily: T.font, background: T.bg, minHeight: "100vh", color: T.text }}>
      <div style={wrap}>
        <button onClick={() => setPage("landing")} style={{ background: "none", border: "none", color: T.text2, cursor: "pointer", fontSize: 13, fontFamily: T.font, padding: "8px 0", marginBottom: 16 }}>← Back</button>
        <h1 style={{ fontSize: 24, fontWeight: 800, marginBottom: 4 }}>Choose Your Trade</h1>
        <p style={{ color: T.text2, fontSize: 14, marginBottom: 24 }}>Select the Red Seal exam you're preparing for</p>
        <div style={{ display: "grid", gap: 10 }}>
          {TRADES.map(t => (
            <div key={t.id}
              onClick={() => { if(t.active) { setTrade(t); setPage("dashboard"); } }}
              style={{
                background: t.active ? `rgba(${hexRgb(t.color)},0.06)` : T.surface,
                border: `1px solid ${t.active ? `rgba(${hexRgb(t.color)},0.2)` : T.border}`,
                borderRadius: T.radius, padding: "16px 18px",
                cursor: t.active ? "pointer" : "default",
                opacity: t.active ? 1 : 0.45,
                display: "flex", alignItems: "center", gap: 14, transition: "all 0.2s"
              }}>
              <div style={{ fontSize: 28 }}>{t.icon}</div>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 700, fontSize: 15 }}>{t.id} — {t.name}</div>
                <div style={{ fontSize: 12, color: T.text2, marginTop: 2 }}>{t.active ? `${t.questions} questions ready` : "Coming soon — join waitlist"}</div>
              </div>
              {t.active && <div style={{ color: t.color, fontSize: 18 }}>→</div>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  // ═══════════════════════════════════════════════════════════
  // DASHBOARD
  // ═══════════════════════════════════════════════════════════
  if (page === "dashboard") {
    const pct = stats.attempted > 0 ? Math.round((stats.correct / stats.attempted) * 100) : 0;
    return (
      <div style={{ fontFamily: T.font, background: T.bg, minHeight: "100vh", color: T.text }}>
        <div style={wrap}>
          <button onClick={() => setPage("trades")} style={{ background: "none", border: "none", color: T.text2, cursor: "pointer", fontSize: 13, fontFamily: T.font, padding: "8px 0" }}>← Trades</button>

          <div style={{ display: "flex", alignItems: "center", gap: 12, margin: "12px 0 20px" }}>
            <div style={{ width: 40, height: 40, background: `linear-gradient(135deg, ${trade?.color || T.accent}, ${T.accent})`, borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20 }}>{trade?.icon}</div>
            <div>
              <div style={{ fontWeight: 800, fontSize: 18 }}>{trade?.id} {trade?.name?.split("(")[0]}</div>
              <div style={{ fontSize: 12, color: T.text2 }}>Red Seal Exam Prep</div>
            </div>
          </div>

          {/* Stats */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, marginBottom: 24 }}>
            {[[`🔥${streak.days}`, "Streak"], [stats.sessions, "Sessions"], [`${pct}%`, "Accuracy"], [`${stats.best}%`, "Best"]].map(([v, l]) => (
              <div key={l} style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10, padding: "12px 8px", textAlign: "center" }}>
                <div style={{ fontSize: 20, fontWeight: 900, color: l === "Accuracy" ? (pct >= 70 ? T.green : T.red) : T.accent2 }}>{v}</div>
                <div style={{ fontSize: 9, color: T.text2, textTransform: "uppercase", letterSpacing: "1px", marginTop: 2 }}>{l}</div>
              </div>
            ))}
          </div>

          {/* Modes */}
          <div style={{ fontSize: 11, fontWeight: 700, color: T.text2, textTransform: "uppercase", letterSpacing: "2px", marginBottom: 10 }}>Practice Modes</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 24 }}>
            {(() => {
              const wb = typeof window !== "undefined" ? JSON.parse(localStorage.getItem("rsp_wrong_" + (trade?.id || "")) || "{}") : {};
              const wrongCount = Object.keys(wb).length;
              const weakCats = getWeakCats();
              const weakLabel = weakCats.length > 0 ? `Block ${weakCats[0].id} (${weakCats[0].pct}%)` : "Complete sessions first";
              return [
              { m: "daily", icon: "⚡", name: "Daily 20", desc: "Quick daily practice", n: 20, free: true },
              { m: "exam", icon: "🎯", name: "Exam Simulator", desc: `Real ${trade?.questions || 120}Q timed exam`, n: trade?.questions || 120, free: false },
              { m: "review", icon: "🔁", name: "Review Wrong", desc: `${wrongCount} saved mistakes`, n: Math.min(wrongCount, 30) || "—", free: false },
              { m: "weak", icon: "📊", name: "Weak Spots", desc: weakLabel, n: 20, free: false },
              { m: "hard", icon: "🧠", name: "Hard Mode", desc: "Critical thinking only", n: 20, free: false },
              { m: "ai", icon: "🤖", name: "AI Tutor", desc: "Ask anything", n: "∞", free: false },
            ];})().map(mode => (
              <div key={mode.m}
                onClick={() => mode.m === "ai" ? setChat(c => ({ ...c, open: true })) : (mode.free || sub) ? startQuiz(mode.m) : setPage("landing")}
                style={{
                  background: T.surface, border: `1px solid ${T.border}`, borderRadius: T.radius,
                  padding: 16, cursor: "pointer", position: "relative", transition: "all 0.2s"
                }}>
                {!mode.free && !sub && <div style={{ position: "absolute", top: 8, right: 8, fontSize: 9, background: "rgba(255,107,53,0.15)", color: T.accent, padding: "2px 6px", borderRadius: 4, fontWeight: 700 }}>PRO</div>}
                <div style={{ fontSize: 10, color: T.accent, fontWeight: 700, marginBottom: 2 }}>{mode.n}Q</div>
                <div style={{ fontSize: 15, marginBottom: 2 }}>{mode.icon} {mode.name}</div>
                <div style={{ fontSize: 11, color: T.text2 }}>{mode.desc}</div>
              </div>
            ))}
          </div>

          {/* Categories */}
          <div style={{ fontSize: 11, fontWeight: 700, color: T.text2, textTransform: "uppercase", letterSpacing: "2px", marginBottom: 10 }}>By Category</div>
          {getCategories().map(cat => (
            <div key={cat.id}
              onClick={() => sub ? startQuiz("cat", cat.id) : setPage("landing")}
              style={{
                background: `rgba(${hexRgb(cat.color)},0.05)`, border: `1px solid rgba(${hexRgb(cat.color)},0.15)`,
                borderRadius: 10, padding: "12px 14px", marginBottom: 8,
                display: "flex", justifyContent: "space-between", alignItems: "center", cursor: "pointer"
              }}>
              <div>
                <div style={{ fontSize: 10, fontWeight: 800, color: cat.color }}>BLOCK {cat.id}</div>
                <div style={{ fontSize: 13, fontWeight: 600 }}>{cat.name}</div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                {!sub && <span style={{ fontSize: 9, color: T.accent }}>PRO</span>}
                <span style={{ fontSize: 12, fontWeight: 700, color: cat.color }}>{cat.target}Q →</span>
              </div>
            </div>
          ))}
        </div>

        {/* AI TUTOR CHAT PANEL */}
        {chat.open && (
          <div style={{ position: "fixed", bottom: 0, left: 0, right: 0, top: 0, background: "rgba(0,0,0,0.7)", zIndex: 200, display: "flex", flexDirection: "column" }}>
            <div style={{ flex: 1, display: "flex", flexDirection: "column", maxWidth: 800, margin: "0 auto", width: "100%" }}>
              <div style={{ padding: "16px 20px", background: T.bg2, borderBottom: `1px solid ${T.border}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ fontWeight: 700, fontSize: 15 }}>🤖 AI Tutor</div>
                <button onClick={() => setChat(c => ({ ...c, open: false }))} style={{ background: "none", border: "none", color: T.text2, cursor: "pointer", fontSize: 20, fontFamily: T.font }}>✕</button>
              </div>
              <div style={{ flex: 1, overflowY: "auto", padding: 16, background: T.bg }}>
                {chat.messages.length === 0 && (
                  <div style={{ textAlign: "center", padding: "40px 20px", color: T.text2 }}>
                    <div style={{ fontSize: 40, marginBottom: 12 }}>🤖</div>
                    <div style={{ fontWeight: 700, fontSize: 16, color: T.text, marginBottom: 8 }}>Ask Me Anything</div>
                    <div style={{ fontSize: 13, lineHeight: 1.6 }}>I'm your Red Seal 433A exam tutor. Ask about hydraulics, alignment, rigging, gear ratios — anything on the exam.</div>
                  </div>
                )}
                {chat.messages.map((m, i) => (
                  <div key={i} style={{ marginBottom: 12, display: "flex", justifyContent: m.role === "user" ? "flex-end" : "flex-start" }}>
                    <div style={{
                      maxWidth: "85%", padding: "12px 16px", borderRadius: 14,
                      background: m.role === "user" ? T.accent : T.bg3,
                      color: T.text, fontSize: 14, lineHeight: 1.6, whiteSpace: "pre-wrap"
                    }}>{m.text}</div>
                  </div>
                ))}
                {chat.loading && <div style={{ color: T.text2, fontSize: 13, padding: 8 }}>Thinking...</div>}
                <div ref={chatEndRef} />
              </div>
              <div style={{ padding: "12px 16px", background: T.bg2, borderTop: `1px solid ${T.border}`, display: "flex", gap: 8 }}>
                <input
                  value={chat.input}
                  onChange={e => setChat(c => ({ ...c, input: e.target.value }))}
                  onKeyDown={e => e.key === "Enter" && sendChat()}
                  placeholder="Ask about any exam topic..."
                  style={{ flex: 1, background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10, padding: "12px 16px", color: T.text, fontSize: 14, fontFamily: T.font, outline: "none" }}
                />
                <button onClick={sendChat} style={{ ...btn(true), width: "auto", padding: "12px 18px" }}>Send</button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ═══════════════════════════════════════════════════════════
  // QUIZ
  // ═══════════════════════════════════════════════════════════
  if (page === "quiz" && quiz) {
    const q = quiz.questions[quiz.idx];
    const cat = getCategories().find(c => c.id === q.cat);
    const pct = ((quiz.idx + (quiz.answered ? 1 : 0)) / quiz.questions.length) * 100;
    const letters = ["A", "B", "C", "D"];

    const getState = (i) => {
      if (!quiz.answered) return null;
      if (i === q.ans) return "correct";
      if (i === quiz.selected && i !== q.ans) return "wrong";
      return null;
    };

    return (
      <div style={{ fontFamily: T.font, background: T.bg, minHeight: "100vh", color: T.text }}>
        <div style={wrap}>
          {/* Progress */}
          <div style={{ height: 4, background: T.surface, borderRadius: 2, overflow: "hidden", marginBottom: 16 }}>
            <div style={{ height: "100%", width: `${pct}%`, background: `linear-gradient(90deg, ${T.accent}, ${T.accent2})`, borderRadius: 2, transition: "width 0.4s" }} />
          </div>

          {/* Meta */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14, flexWrap: "wrap", gap: 6 }}>
            <span style={{ fontSize: 12, color: T.text2, fontWeight: 600 }}>Q{quiz.idx + 1}/{quiz.questions.length}</span>
            <span style={{ fontSize: 10, color: cat.color, background: `rgba(${hexRgb(cat.color)},0.12)`, padding: "2px 8px", borderRadius: 4, fontWeight: 700 }}>Block {q.cat}</span>
            <span style={{ fontSize: 10, color: T.text2, background: T.surface, padding: "2px 8px", borderRadius: 4 }}>
              {q.type === "recall" ? "📖 Recall" : q.type === "procedure" ? "🔧 Procedure" : "🧠 Critical"}
            </span>
            <span style={{ fontSize: 12, color: quiz.countdown > 0 && (quiz.countdown - quiz.timer) < 600 ? T.red : T.accent2, fontWeight: 700, fontFamily: T.mono }}>
              {quiz.countdown > 0 ? `⏱ ${fmtTime(Math.max(0, quiz.countdown - quiz.timer))} left` : `⏱ ${fmtTime(quiz.timer)}`}
            </span>
            {quiz.mode === "exam" && <span style={{ fontSize: 9, background: "rgba(255,107,53,0.15)", color: T.accent, padding: "2px 6px", borderRadius: 4, fontWeight: 700 }}>EXAM MODE</span>}
            {quiz.mode === "review" && <span style={{ fontSize: 9, background: "rgba(76,175,80,0.15)", color: T.green, padding: "2px 6px", borderRadius: 4, fontWeight: 700 }}>REVIEW</span>}
          </div>

          {/* Question */}
          <div style={{ fontSize: "clamp(0.95rem, 2.5vw, 1.15rem)", fontWeight: 700, lineHeight: 1.55, marginBottom: 20 }}>{q.q}</div>

          {/* Options */}
          {q.opts.map((opt, i) => {
            const st = getState(i);
            const bg = st === "correct" ? `rgba(${hexRgb(T.green)},0.1)` : st === "wrong" ? `rgba(${hexRgb(T.red)},0.1)` : T.surface;
            const bdr = st === "correct" ? T.green : st === "wrong" ? T.red : T.border;
            return (
              <div key={i} onClick={() => selectAnswer(i)} style={{
                background: bg, border: `2px solid ${bdr}`, borderRadius: 10, padding: "14px 16px",
                marginBottom: 8, display: "flex", alignItems: "center", gap: 12, cursor: quiz.answered ? "default" : "pointer", transition: "all 0.2s"
              }}>
                <div style={{
                  width: 30, height: 30, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 13, fontWeight: 800, flexShrink: 0,
                  background: st === "correct" ? `rgba(${hexRgb(T.green)},0.2)` : st === "wrong" ? `rgba(${hexRgb(T.red)},0.2)` : T.surface,
                  color: st === "correct" ? T.green : st === "wrong" ? T.red : T.text2
                }}>
                  {quiz.answered && st === "correct" ? "✓" : quiz.answered && st === "wrong" ? "✗" : letters[i]}
                </div>
                <div style={{ fontSize: "clamp(0.82rem, 2vw, 0.95rem)", lineHeight: 1.4, color: st ? (st === "correct" ? T.green : T.red) : T.text }}>{opt}</div>
              </div>
            );
          })}

          {/* Explanation */}
          {quiz.answered && (
            <div style={{ background: "rgba(255,167,38,0.06)", border: "1px solid rgba(255,167,38,0.15)", borderRadius: 10, padding: 14, marginTop: 16, fontSize: 13, lineHeight: 1.65, color: "#c4a35a" }}>
              <strong style={{ color: T.accent2 }}>💡 </strong>{q.exp}
            </div>
          )}

          {/* Actions */}
          {quiz.answered && (
            <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
              {sub && <button onClick={() => setChat(c => ({ ...c, open: true }))} style={{ ...btn(false), flex: "0 0 auto", width: "auto", padding: "14px 16px", fontSize: 18 }}>🤖</button>}
              <button onClick={nextQ} style={{ ...btn(true), flex: 1 }}>
                {quiz.idx < quiz.questions.length - 1 ? "Next →" : "See Results →"}
              </button>
            </div>
          )}

          <div style={{ textAlign: "center", marginTop: 16 }}>
            <button onClick={() => { setQuiz(null); setPage("dashboard"); }} style={{ background: "none", border: "none", color: T.text2, cursor: "pointer", fontSize: 13, fontFamily: T.font }}>← Exit Quiz</button>
          </div>
        </div>

        {/* AI Chat overlay in quiz too */}
        {chat.open && (
          <div style={{ position: "fixed", bottom: 0, left: 0, right: 0, height: "60vh", background: T.bg2, zIndex: 200, display: "flex", flexDirection: "column", borderTop: `2px solid ${T.accent}`, borderRadius: "16px 16px 0 0" }}>
            <div style={{ padding: "12px 20px", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: `1px solid ${T.border}` }}>
              <span style={{ fontWeight: 700, fontSize: 14 }}>🤖 AI Tutor — ask about this question</span>
              <button onClick={() => setChat(c => ({ ...c, open: false }))} style={{ background: "none", border: "none", color: T.text2, cursor: "pointer", fontSize: 18 }}>✕</button>
            </div>
            <div style={{ flex: 1, overflowY: "auto", padding: 12 }}>
              {chat.messages.map((m, i) => (
                <div key={i} style={{ marginBottom: 8, display: "flex", justifyContent: m.role === "user" ? "flex-end" : "flex-start" }}>
                  <div style={{ maxWidth: "85%", padding: "10px 14px", borderRadius: 12, background: m.role === "user" ? T.accent : T.bg3, fontSize: 13, lineHeight: 1.5, whiteSpace: "pre-wrap" }}>{m.text}</div>
                </div>
              ))}
              {chat.loading && <div style={{ color: T.text2, fontSize: 12, padding: 8 }}>Thinking...</div>}
              <div ref={chatEndRef} />
            </div>
            <div style={{ padding: "10px 12px", display: "flex", gap: 8, borderTop: `1px solid ${T.border}` }}>
              <input value={chat.input} onChange={e => setChat(c => ({ ...c, input: e.target.value }))} onKeyDown={e => e.key === "Enter" && sendChat()}
                placeholder="Why is B correct?" style={{ flex: 1, background: T.surface, border: `1px solid ${T.border}`, borderRadius: 8, padding: "10px 12px", color: T.text, fontSize: 13, fontFamily: T.font, outline: "none" }} />
              <button onClick={sendChat} style={{ ...btn(true), width: "auto", padding: "10px 16px", fontSize: 13 }}>→</button>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ═══════════════════════════════════════════════════════════
  // RESULTS
  // ═══════════════════════════════════════════════════════════
  if (page === "results" && quiz) {
    const pct = Math.round((quiz.score / quiz.questions.length) * 100);
    const passed = pct >= 70;

    const catBreak = getCategories().map(cat => {
      const qs = quiz.answers.filter(a => quiz.questions.find(q => q.id === a.qId)?.cat === cat.id);
      const ok = qs.filter(a => a.ok).length;
      return { ...cat, total: qs.length, ok, pct: qs.length ? Math.round((ok / qs.length) * 100) : 0 };
    }).filter(c => c.total > 0);

    return (
      <div style={{ fontFamily: T.font, background: T.bg, minHeight: "100vh", color: T.text }}>
        <div style={wrap}>
          <div style={{ textAlign: "center", margin: "20px 0 24px" }}>
            <div style={{ fontSize: 36, marginBottom: 12 }}>{passed ? "🏆" : "📚"}</div>
            <div style={{
              width: 130, height: 130, borderRadius: "50%", margin: "0 auto 16px",
              background: `linear-gradient(135deg, rgba(${hexRgb(passed ? T.green : T.red)},0.15), rgba(${hexRgb(passed ? T.green : T.red)},0.05))`,
              border: `3px solid ${passed ? T.green : T.red}`,
              display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center"
            }}>
              <div style={{ fontSize: 40, fontWeight: 900, color: passed ? T.green : T.red, lineHeight: 1 }}>{pct}%</div>
              <div style={{ fontSize: 13, fontWeight: 600, color: passed ? T.green : T.red, marginTop: 2 }}>{quiz.score}/{quiz.questions.length}</div>
            </div>
            <div style={{ fontSize: 18, fontWeight: 800, color: passed ? T.green : T.red }}>
              {quiz.mode === "exam" ? (passed ? "RED SEAL READY! 🏆" : "NOT YET — KEEP GOING 💪") : (passed ? "PASSED! 🎉" : "KEEP STUDYING")}
            </div>
            {quiz.mode === "exam" && <div style={{ fontSize: 11, color: T.text2, marginTop: 4, background: T.surface, display: "inline-block", padding: "4px 10px", borderRadius: 6 }}>
              Exam Simulation: {quiz.questions.length} questions in {fmtTime(quiz.timer)}
            </div>}
            <div style={{ fontSize: 12, color: T.text2, marginTop: 4 }}>Time: {fmtTime(quiz.timer)} • {Math.round(quiz.timer / quiz.questions.length)}s avg</div>
          </div>

          {/* Category breakdown */}
          <div style={{ marginBottom: 20 }}>
            {catBreak.map(c => (
              <div key={c.id} style={{ marginBottom: 10 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 3 }}>
                  <span style={{ color: c.color, fontWeight: 700 }}>Block {c.id}</span>
                  <span style={{ color: c.pct >= 70 ? T.green : T.red, fontWeight: 800 }}>{c.ok}/{c.total} ({c.pct}%)</span>
                </div>
                <div style={{ height: 6, background: T.surface, borderRadius: 3 }}>
                  <div style={{ height: "100%", width: `${c.pct}%`, background: c.pct >= 70 ? c.color : T.red, borderRadius: 3, transition: "width 0.5s" }} />
                </div>
              </div>
            ))}
          </div>

          {/* Wrong answers review */}
          <button onClick={() => setShowWrong(!showWrong)} style={{ ...btn(false), marginBottom: 12 }}>
            {showWrong ? "Hide" : "📝 Review"} Wrong Answers ({quiz.answers.filter(a => !a.ok).length})
          </button>

          {showWrong && quiz.answers.filter(a => !a.ok).map((a, i) => {
            const q = getQuestions().find(q => q.id === a.qId);
            if (!q) return null;
            return (
              <div key={i} style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10, padding: 14, marginBottom: 8 }}>
                <div style={{ fontWeight: 700, color: T.red, fontSize: 11, marginBottom: 4 }}>✗ Q{q.id}</div>
                <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>{q.q}</div>
                <div style={{ fontSize: 12, color: T.red }}>Yours: {q.opts[a.sel]}</div>
                <div style={{ fontSize: 12, color: T.green, fontWeight: 700 }}>Correct: {q.opts[q.ans]}</div>
                <div style={{ fontSize: 11, color: "#c4a35a", marginTop: 6, lineHeight: 1.5 }}>{q.exp}</div>
              </div>
            );
          })}

          {/* Weak Spot Analysis */}
          {(() => {
            const weak = getWeakCats();
            if (weak.length === 0) return null;
            const worst = weak.filter(c => c.pct < 70).slice(0, 3);
            if (worst.length === 0) return null;
            return (
              <div style={{ background: "rgba(255,107,53,0.05)", border: `1px solid rgba(255,107,53,0.15)`, borderRadius: 10, padding: 14, marginTop: 16, marginBottom: 8 }}>
                <div style={{ fontSize: 12, fontWeight: 800, color: T.accent, marginBottom: 8 }}>📊 YOUR WEAK SPOTS</div>
                {worst.map(c => (
                  <div key={c.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 12, marginBottom: 6 }}>
                    <span style={{ color: T.text }}>Block {c.id}: {c.name}</span>
                    <span style={{ color: T.red, fontWeight: 700 }}>{c.pct}%</span>
                  </div>
                ))}
                <button onClick={() => sub ? startQuiz("weak") : setPage("landing")} style={{ ...btn(true), marginTop: 8, padding: "10px 16px", fontSize: 13 }}>🎯 Drill Weakest Category</button>
              </div>
            );
          })()}

          {/* Spaced repetition prompt */}
          {Object.keys(wrongBank).length > 0 && (
            <button onClick={() => startQuiz("review")} style={{ ...btn(false), marginTop: 8, marginBottom: 8, border: `1px solid ${T.green}`, color: T.green }}>
              🔁 Review {Object.keys(wrongBank).length} Saved Mistakes
            </button>
          )}

          {/* Email capture — nudge anonymous users to save this result */}
          {supabase && !authUser && (
            <div style={{ background: "rgba(88,166,255,0.06)", border: "1px solid rgba(88,166,255,0.2)", borderRadius: 10, padding: 14, marginTop: 16, display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <div style={{ fontSize: 12, color: T.text2, lineHeight: 1.5 }}>
                <b style={{ color: T.text }}>☁️ Don&apos;t lose this progress.</b> Sign in free to keep your scores and streak on any device.
              </div>
              <button onClick={() => setShowSignIn(true)} style={{ ...btn(false), width: "auto", padding: "9px 16px", fontSize: 12, whiteSpace: "nowrap" }}>Sign in free →</button>
            </div>
          )}

          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <button onClick={() => { setQuiz(null); setPage("dashboard"); }} style={{ ...btn(false), flex: 1 }}>← Dashboard</button>
            <button onClick={() => startQuiz("daily")} style={{ ...btn(true), flex: 1 }}>🔄 Quick 20</button>
          </div>
        </div>
        {signInModal}
      </div>
    );
  }

  return null;
}
