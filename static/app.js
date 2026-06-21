/* เงาเหนือมอร์นโฮลโลว์ — ตรรกะหน้าเว็บ (แชต + ทอยเต๋า + เซฟหลายเกม) */
const SAVES_KEY = "mournhollow_saves_v1";
const $ = (id) => document.getElementById(id);
const chat = $("chat");

let pick = { hero: null, klass: null, mode: "A", campaign: "เงาเหนือมอร์นโฮลโลว์" };
let history = [];          // [{role:'user'|'model', text}] -> ส่งให้ API
let lastState = null;
let gameId = null;
let busy = false;
let lastRoll = null;

/* ===================== ระบบเซฟหลายเกม ===================== */
function allSaves() {
  try { return JSON.parse(localStorage.getItem(SAVES_KEY)) || { current: null, slots: {} }; }
  catch (e) { return { current: null, slots: {} }; }
}
function writeSaves(o) { localStorage.setItem(SAVES_KEY, JSON.stringify(o)); }
function uid() { return Date.now().toString(36) + Math.random().toString(36).slice(2, 6); }

function saveCurrent() {
  if (!gameId) return;
  const s = allSaves();
  s.slots[gameId] = {
    name: `${pick.hero || "ฮีโร่"} · โหมด ${pick.mode}`,
    pick, history, lastState,
    updated: Date.now(),
    created: (s.slots[gameId] && s.slots[gameId].created) || Date.now(),
  };
  s.current = gameId;
  writeSaves(s);
}
function newGame(hero, klass, mode) {
  gameId = uid();
  pick = { hero, klass, mode };
  history = []; lastState = null;
  const s = allSaves(); s.current = gameId; writeSaves(s);
  saveCurrent();
}
function loadGame(id) {
  const s = allSaves(); const slot = s.slots[id];
  if (!slot) return;
  gameId = id; pick = slot.pick || pick; history = slot.history || [];
  lastState = slot.lastState || null;
  s.current = id; writeSaves(s);
  chat.innerHTML = "";
  $("setup").classList.add("hidden");
  closeDrawer(); applyModeUI(); restore();
}
function deleteGame(id) {
  const s = allSaves(); delete s.slots[id];
  if (s.current === id) s.current = null;
  writeSaves(s);
  if (gameId === id) { gameId = null; }
  renderSaves();
}

/* ===================== แสดงข้อความ ===================== */
function escapeHtml(s) {
  return String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}
function fmtInline(s) {
  s = s.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
  s = s.replace(/("[^"]*"|“[^”]*”|「[^」]*」|«[^»]*»)/g, '<span class="say">$1</span>');
  s = s.replace(/\((?:d20|d\d+|ทอย|เต๋า)[^)]*\)/g, (m) => `<span class="roll">${m}</span>`);
  return s;
}
function formatGM(raw) {
  const lines = escapeHtml(raw).split("\n");
  let html = "";
  for (const ln of lines) {
    const t = ln.trim();
    if (!t) { html += '<div class="pgap"></div>'; continue; }
    const m = t.match(/^([^:：<][^:：]{0,24})[:：]\s*(["“「«].*)$/);
    if (m) {
      html += `<div class="dlg"><span class="spk">${m[1]}</span><span class="dtxt">: ${fmtInline(m[2])}</span></div>`;
    } else {
      html += `<div class="narr">${fmtInline(t)}</div>`;
    }
  }
  return html;
}
function bubble(kind, text) {
  const div = document.createElement("div");
  div.className = "msg " + kind;
  const who = kind === "gm" ? "GM" : kind === "you" ? "คุณ" : "";
  let html = who ? `<div class="who">${who}</div>` : "";
  html += kind === "gm"
    ? formatGM(text)
    : escapeHtml(text).replace(/\((?:d20|d\d+|ทอย|เต๋า)[^)]*\)/g, (m) => `<span class="roll">${m}</span>`);
  div.innerHTML = html;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

/* ===================== บล็อกสถานะ ===================== */
function parseState(text) {
  const m = text.match(/\[\[STATE\]\]([\s\S]*?)\[\[\/STATE\]\]/);
  const clean = text.replace(/\[\[STATE\]\][\s\S]*?\[\[\/STATE\]\]/g, "").trim();
  let state = null;
  if (m) { try { state = JSON.parse(m[1].trim()); } catch (e) {} }
  return { clean, state };
}
function updatePanel(s) {
  if (!s) return;
  lastState = s;
  const set = (id, v) => { if (v !== undefined && v !== null) $(id).textContent = v; };
  set("sName", s.name); set("sKlass", s.klass); set("sLevel", s.level);
  set("sMode", s.mode || pick.mode); set("sAc", s.ac);
  set("sLoc", s.location); set("sGold", s.gold); set("sClock", s.clock || "0/6");
  if (s.hp !== undefined && s.max_hp) {
    $("sHpTxt").textContent = `${s.hp} / ${s.max_hp}`;
    $("sHpFill").style.width = Math.max(0, Math.min(100, (s.hp / s.max_hp) * 100)) + "%";
  }
  const cond = $("sCond");
  cond.innerHTML = (Array.isArray(s.conditions) && s.conditions.length)
    ? s.conditions.map((c) => `<span class="chip">${escapeHtml(c)}</span>`).join("")
    : `<span class="muted">ปกติ</span>`;
  if (s.alive === false) $("sName").innerHTML = escapeHtml(s.name || "") + " ☠";
  renderHotbar(s);
  renderXp(s); renderCombat(s.combat); renderMap(s.map, s.location); renderParty(s.party);
}

let HOTCODES = {};
function renderHotbar(s) {
  const hb = document.getElementById("hotbar");
  HOTCODES = {};
  const skills = Array.isArray(s.skills) ? s.skills : [];
  const items = Array.isArray(s.items) ? s.items : [];
  if (!skills.length && !items.length) { hb.hidden = true; hb.innerHTML = ""; return; }
  let html = "";
  if (skills.length) {
    html += '<div class="hb-group"><span class="hb-head">⚔️ สกิล</span>';
    skills.forEach((sk, i) => {
      const code = "S" + (i + 1);
      const name = sk && sk.n ? sk.n : String(sk);
      HOTCODES[code.toLowerCase()] = name;
      const d = sk && sk.d ? ` <span class="hb-d">${escapeHtml(sk.d)}</span>` : "";
      html += `<button class="hb-chip" data-name="${escapeHtml(name)}"><span class="hb-code">${code}</span> ${escapeHtml(name)}${d}</button>`;
    });
    html += "</div>";
  }
  if (items.length) {
    html += '<div class="hb-group"><span class="hb-head">🎒 ไอเท็ม</span>';
    items.forEach((it, i) => {
      const code = "I" + (i + 1);
      const name = it && it.n ? it.n : String(it);
      HOTCODES[code.toLowerCase()] = name;
      const q = it && it.q ? ` ×${it.q}` : "";
      html += `<button class="hb-chip item" data-name="${escapeHtml(name)}"><span class="hb-code">${code}</span> ${escapeHtml(name)}${q}</button>`;
    });
    html += "</div>";
  }
  hb.innerHTML = html;
  hb.hidden = false;
}

function renderXp(s) {
  if (s.xp !== undefined && s.xp_next) {
    $("sXpFill").style.width = Math.max(0, Math.min(100, (s.xp / s.xp_next) * 100)) + "%";
    $("sXpTxt").textContent = `XP ${s.xp} / ${s.xp_next}`;
  } else { $("sXpFill").style.width = "0%"; $("sXpTxt").textContent = ""; }
}
function renderCombat(cb) {
  const card = $("combatCard");
  if (!cb || !cb.active || !Array.isArray(cb.enemies) || !cb.enemies.length) { card.classList.add("hidden"); return; }
  card.classList.remove("hidden");
  $("cbRound").textContent = "รอบ " + (cb.round || 1) + (cb.turn ? " · ตา: " + cb.turn : "");
  $("cbEnemies").innerHTML = cb.enemies.map((e) => {
    const mx = e.max_hp || e.hp || 1;
    const pct = Math.max(0, Math.min(100, (e.hp != null ? e.hp / mx : 1) * 100));
    const turn = (cb.turn && e.n === cb.turn) ? " turn" : "";
    const cond = e.cond ? `<div class="en-cond">${escapeHtml(e.cond)}</div>` : "";
    return `<div class="enemy"><div class="en-top"><span class="en-name${turn}">${escapeHtml(e.n || "ศัตรู")}</span><span class="en-hp">${e.hp != null ? e.hp : "?"}/${mx}</span></div><div class="ehpbar"><div class="ehpfill" style="width:${pct}%"></div></div>${cond}</div>`;
  }).join("");
}
function renderMap(map, here) {
  here = here || "";
  $("sMap").innerHTML = (Array.isArray(map) && map.length)
    ? map.map((r) => `<span class="room${r === here ? " here" : ""}" data-go="${escapeHtml(r)}">${r === here ? "📍 " : ""}${escapeHtml(r)}</span>`).join("")
    : `<span class="muted">—</span>`;
}
function renderParty(party) {
  const card = $("partyCard");
  if (!Array.isArray(party) || !party.length) { card.classList.add("hidden"); return; }
  card.classList.remove("hidden");
  $("sParty").innerHTML = party.map((a) => {
    const mx = a.max_hp || a.hp || 1;
    const pct = Math.max(0, Math.min(100, (a.hp != null ? a.hp / mx : 1) * 100));
    const note = a.note ? `<span class="al-note">${escapeHtml(a.note)}</span>` : "";
    return `<div class="ally"><div class="al-top"><span class="al-name">${escapeHtml(a.n || "เพื่อน")}</span>${note}</div><div class="ahpbar"><div class="ahpfill" style="width:${pct}%"></div></div><div class="al-note" style="text-align:right">HP ${a.hp != null ? a.hp : "?"}/${mx}</div></div>`;
  }).join("");
}

/* ===================== เรียก GM ===================== */
function addRetry() {
  const d = document.createElement("div");
  d.className = "msg sys";
  d.innerHTML = '<button class="retry">🔄 ลองอีกครั้ง</button>';
  d.querySelector(".retry").onclick = () => { d.remove(); callGM(); };
  chat.appendChild(d); chat.scrollTop = chat.scrollHeight;
}
async function callGM() {
  if (busy) return;
  busy = true; $("sendBtn").disabled = true; $("typing").hidden = false;
  chat.scrollTop = chat.scrollHeight;
  try {
    const res = await fetch("/api/chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: history }),
    });
    const data = await res.json();
    if (!res.ok || data.error) {
      bubble("sys", "⚠️ " + (data.error || ("HTTP " + res.status)));
      addRetry();
    } else {
      history.push({ role: "model", text: data.text });
      const { clean, state } = parseState(data.text);
      bubble("gm", clean || "…");
      if (state) updatePanel(state);
      saveCurrent();
    }
  } catch (e) {
    bubble("sys", "⚠️ เชื่อมต่อเซิร์ฟเวอร์ไม่ได้: " + e.message);
    addRetry();
  } finally {
    busy = false; $("sendBtn").disabled = false; $("typing").hidden = true;
    chat.scrollTop = chat.scrollHeight;
  }
}
function sendUser(text, displayKind = "you") {
  if (!text.trim() || busy) return;
  history.push({ role: "user", text });
  if (displayKind) bubble(displayKind, text);
  saveCurrent(); callGM();
}

/* ===================== เริ่มเกม ===================== */
function kickoff() {
  const { hero, klass, mode, campaign } = pick;
  let msg;
  if (mode === "C") {
    msg = `เริ่มเกมโหมด C เล่นแคมเปญ "${campaign}" ใช้ฮีโร่ "${hero}" (${klass}) โดยคุณ(AI)สวมบทฮีโร่และคิดเองด้วย เล่นทั้ง [GM] และ [ฮีโร่] ` +
      `จัดชีตระดับ 1 แล้วเปิด "ฉากเปิด" ของแคมเปญนี้ เดินเรื่อง 1 จังหวะแล้วหยุดให้ฉันกำกับ ` +
      `ฮีโร่ต้องไม่รู้ความจริงเบื้องหลังหรือค่าพลังศัตรู และอย่าลืมแนบบล็อก [[STATE]] ท้ายคำตอบ`;
  } else {
    msg = `เริ่มเกมโหมด A เล่นแคมเปญ "${campaign}" ฉันขอเล่นเป็นฮีโร่ "${hero}" (${klass}) ด้วยตัวเอง ` +
      `จัดชีตระดับ 1 แล้วเปิด "ฉากเปิด" ของแคมเปญนี้ จบด้วยการถามว่าฉันจะทำอะไร และอย่าลืมแนบบล็อก [[STATE]] ท้ายคำตอบ`;
  }
  bubble("sys", `⚔️ เริ่มเกม · ${campaign} · ฮีโร่ ${hero} (${klass}) · โหมด ${mode}`);
  history.push({ role: "user", text: msg });
  saveCurrent(); callGM();
}
function restore() {
  history.forEach((m, i) => {
    if (m.role === "model") { bubble("gm", parseState(m.text).clean); }
    else if (i === 0 && /เริ่มเกมโหมด/.test(m.text)) { bubble("sys", `⚔️ เริ่มเกม · ${pick.campaign || ""} · ฮีโร่ ${pick.hero} (${pick.klass}) · โหมด ${pick.mode}`); }
    else if (m.text === "(เดินเรื่องต่อ)") { bubble("sys", "▶ เดินเรื่องต่อ"); }
    else { bubble("you", m.text); }
  });
  if (lastState) updatePanel(lastState);
  // ถ้าตาสุดท้ายเป็นของผู้เล่นแต่ GM ยังไม่ตอบ (เช่นเจอ error แล้วรีเฟรช) ให้เดินเรื่องต่อเอง
  if (history.length && history[history.length - 1].role === "user") callGM();
}

/* ===================== ทอยเต๋า (crypto จริง) ===================== */
function rollInt(sides) {
  const a = new Uint32Array(1); crypto.getRandomValues(a);
  return (a[0] % sides) + 1;
}
function rollDice(sides) {
  const mod = parseInt($("diceMod").value, 10) || 0;
  const adv = parseInt(document.querySelector('input[name="adv"]:checked').value, 10);
  let face, detail = "";
  if (sides === 20 && adv !== 0) {
    const r1 = rollInt(20), r2 = rollInt(20);
    face = adv > 0 ? Math.max(r1, r2) : Math.min(r1, r2);
    detail = ` ${adv > 0 ? "ได้เปรียบ" : "เสียเปรียบ"} [${r1},${r2}]→${face}`;
  } else { face = rollInt(sides); }
  const total = face + mod;
  const modStr = mod ? (mod > 0 ? `+${mod}` : `${mod}`) : "";
  const plain = `ทอย d${sides}${modStr} = ${total} (เต๋า ${face}${detail ? "," + detail : ""})`;
  let cls = "";
  if (sides === 20 && face === 20) cls = "crit";
  else if (sides === 20 && face === 1) cls = "fail";
  const tag = cls === "crit" ? " ✦ คริติคอล!" : cls === "fail" ? " ✗ พลาดวิกฤต" : "";
  $("diceResult").innerHTML = `🎲 <b>d${sides}${modStr}</b>${detail} = <b class="${cls}">${total}</b>${tag}`;
  lastRoll = plain;
  $("diceSend").hidden = false;
}

/* ===================== เมนูเซฟ ===================== */
function fmtTime(t) { try { return new Date(t).toLocaleString("th-TH", { dateStyle: "short", timeStyle: "short" }); } catch (e) { return ""; } }
function renderSaves() {
  const s = allSaves();
  const ids = Object.keys(s.slots).sort((a, b) => s.slots[b].updated - s.slots[a].updated);
  const list = $("savesList");
  if (!ids.length) { list.innerHTML = `<div class="empty">ยังไม่มีเกมที่บันทึก</div>`; return; }
  list.innerHTML = ids.map((id) => {
    const sl = s.slots[id];
    const turns = (sl.history || []).filter((m) => m.role === "model").length;
    const cur = id === gameId ? " cur" : "";
    const hp = sl.lastState && sl.lastState.hp !== undefined ? ` · HP ${sl.lastState.hp}/${sl.lastState.max_hp || "?"}` : "";
    return `<div class="save-item${cur}">
      <div class="si-name">${escapeHtml(sl.name)}${id === gameId ? " (กำลังเล่น)" : ""}</div>
      <div class="si-meta">${turns} ฉาก${hp} · ${fmtTime(sl.updated)}</div>
      <div class="si-btns"><button class="load" data-id="${id}">โหลด</button><button class="del" data-id="${id}">ลบ</button></div>
    </div>`;
  }).join("");
}
function openDrawer() { renderSaves(); $("saves").classList.remove("hidden"); }
function closeDrawer() { $("saves").classList.add("hidden"); }

/* ===================== โหมด UI ===================== */
function applyModeUI() {
  $("contBtn").hidden = pick.mode !== "C";
  $("sMode").textContent = pick.mode;
}

/* ===================== อีเวนต์ ===================== */
$("heroPick").addEventListener("click", (e) => {
  const b = e.target.closest(".hero"); if (!b) return;
  document.querySelectorAll(".hero").forEach((x) => x.classList.remove("sel"));
  b.classList.add("sel");
  pick.hero = b.dataset.hero; pick.klass = b.dataset.klass;
  $("startBtn").disabled = false;
  $("startBtn").textContent = `เริ่มเกมกับ ${pick.hero} ▶`;
});
$("campPick").addEventListener("click", (e) => {
  const b = e.target.closest(".mode"); if (!b) return;
  document.querySelectorAll("#campPick .mode").forEach((x) => x.classList.remove("sel"));
  b.classList.add("sel"); pick.campaign = b.dataset.camp;
});
$("modePick").addEventListener("click", (e) => {
  const b = e.target.closest(".mode"); if (!b) return;
  document.querySelectorAll("#modePick .mode").forEach((x) => x.classList.remove("sel"));
  b.classList.add("sel"); pick.mode = b.dataset.mode;
  $("setupHint").textContent = pick.mode === "C"
    ? "โหมด C: นั่งดู AI เล่นเอง กดปุ่ม ‘▶ ต่อ’ เพื่อเดินเรื่อง หรือพิมพ์กำกับได้"
    : "โหมด A: พิมพ์สิ่งที่ตัวละครจะทำในแต่ละตา";
});
$("startBtn").addEventListener("click", () => {
  if (!pick.hero) return;
  chat.innerHTML = "";
  newGame(pick.hero, pick.klass, pick.mode);
  $("setup").classList.add("hidden");
  applyModeUI(); kickoff();
});
$("setup").addEventListener("click", (e) => {
  // คลิกพื้นหลังเพื่อปิด (เฉพาะเมื่อมีเกมกำลังเล่นอยู่)
  if (e.target.id === "setup" && gameId) $("setup").classList.add("hidden");
});

$("sendBtn").addEventListener("click", () => {
  let t = $("input").value;
  const code = t.trim().toLowerCase();
  if (HOTCODES[code]) t = "ใช้ " + HOTCODES[code];   // พิมพ์รหัสย่อ เช่น s1 / i2
  $("input").value = ""; autosize(); sendUser(t);
});
$("contBtn").addEventListener("click", () => sendUser("(เดินเรื่องต่อ)", "sys"));
document.getElementById("hotbar").addEventListener("click", (e) => {
  const b = e.target.closest(".hb-chip"); if (!b) return;
  const inp = $("input");
  inp.value = "ใช้ " + b.dataset.name + " ";
  inp.focus(); autosize();
});
$("sMap").addEventListener("click", (e) => {
  const r = e.target.closest(".room"); if (!r || r.classList.contains("here")) return;
  sendUser("เดินทางไป " + r.dataset.go);
});
$("input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("sendBtn").click(); }
});
$("input").addEventListener("input", autosize);
function autosize() { const el = $("input"); el.style.height = "auto"; el.style.height = Math.min(160, el.scrollHeight) + "px"; }

/* ปุ่มทอยเต๋า */
$("diceToggle").addEventListener("click", () => {
  const p = $("dicePanel"); p.hidden = !p.hidden;
});
document.querySelector(".dieBtns").addEventListener("click", (e) => {
  const b = e.target.closest(".die"); if (!b) return;
  rollDice(parseInt(b.dataset.d, 10));
});
$("diceSend").addEventListener("click", () => {
  if (!lastRoll) return;
  sendUser("(ผลทอยของฉัน: " + lastRoll + ")", "you");
  $("diceSend").hidden = true;
});

/* เมนูเซฟ */
$("savesBtn").addEventListener("click", openDrawer);
$("savesClose").addEventListener("click", closeDrawer);
$("saves").addEventListener("click", (e) => { if (e.target.id === "saves") closeDrawer(); });
$("savesList").addEventListener("click", (e) => {
  const b = e.target.closest("button"); if (!b) return;
  const id = b.dataset.id;
  if (b.classList.contains("load")) loadGame(id);
  else if (b.classList.contains("del")) { if (confirm("ลบเกมนี้?")) deleteGame(id); }
});
$("newGameBtn").addEventListener("click", () => { closeDrawer(); $("setup").classList.remove("hidden"); });
$("resetBtn").addEventListener("click", () => {
  document.querySelectorAll(".hero").forEach((x) => x.classList.remove("sel"));
  $("startBtn").disabled = true; $("startBtn").textContent = "เลือกฮีโร่ก่อน…";
  $("setup").classList.remove("hidden");
});

/* ===================== การเชื่อมต่อ ===================== */
async function checkHealth() {
  try {
    const r = await fetch("/api/health"); const d = await r.json();
    const c = $("conn");
    if (d.key_set) { c.className = "conn ok"; c.title = "เชื่อมต่อแล้ว · " + (d.active_model || d.models[0]); }
    else { c.className = "conn bad"; c.title = "ยังไม่ได้ตั้งค่า GEMINI_API_KEY บนเซิร์ฟเวอร์"; }
  } catch (e) { $("conn").className = "conn bad"; }
}

/* ===================== บูต ===================== */
checkHealth();
(function boot() {
  const s = allSaves();
  if (s.current && s.slots[s.current]) {
    loadGame(s.current);
  }
})();
