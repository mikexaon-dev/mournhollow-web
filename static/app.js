/* เงาเหนือมอร์นโฮลโลว์ — ตรรกะฝั่งหน้าเว็บ */
const LS = "mournhollow_save_v1";
let pick = { hero: null, klass: null, mode: "A" };
let history = [];          // [{role:'user'|'model', text}]  -> ส่งให้ API
let started = false;
let busy = false;
let lastState = null;

const $ = (id) => document.getElementById(id);
const chat = $("chat");

/* ---------- โหลด/บันทึก ---------- */
function save() {
  localStorage.setItem(LS, JSON.stringify({ history, pick, started, lastState }));
}
function load() {
  try {
    const d = JSON.parse(localStorage.getItem(LS) || "null");
    if (d && d.started) {
      history = d.history || [];
      pick = d.pick || pick;
      lastState = d.lastState || null;
      started = true;
      return true;
    }
  } catch (e) {}
  return false;
}

/* ---------- แสดงข้อความ ---------- */
function bubble(kind, text) {
  const div = document.createElement("div");
  div.className = "msg " + kind;
  const who = kind === "gm" ? "GM" : kind === "you" ? "คุณ" : "";
  let html = "";
  if (who) html += `<div class="who">${who}</div>`;
  html += escapeHtml(text).replace(
    /\((?:d20|d\d+|ทอย)[^)]*\)/g,
    (m) => `<span class="roll">${m}</span>`
  );
  div.innerHTML = html;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}
function escapeHtml(s) {
  return s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}

/* ---------- แยกบล็อกสถานะ ---------- */
function parseState(text) {
  const m = text.match(/\[\[STATE\]\]([\s\S]*?)\[\[\/STATE\]\]/);
  let clean = text.replace(/\[\[STATE\]\][\s\S]*?\[\[\/STATE\]\]/g, "").trim();
  let state = null;
  if (m) {
    try { state = JSON.parse(m[1].trim()); } catch (e) {}
  }
  return { clean, state };
}

/* ---------- อัปเดตแผงสถานะ ---------- */
function updatePanel(s) {
  if (!s) return;
  lastState = s;
  const set = (id, v) => { if (v !== undefined && v !== null) $(id).textContent = v; };
  set("sName", s.name);
  set("sKlass", s.klass);
  set("sLevel", s.level);
  set("sMode", s.mode || pick.mode);
  set("sAc", s.ac);
  set("sLoc", s.location);
  set("sGold", s.gold);
  set("sClock", s.clock || "0/6");
  if (s.hp !== undefined && s.max_hp) {
    $("sHpTxt").textContent = `${s.hp} / ${s.max_hp}`;
    const pct = Math.max(0, Math.min(100, (s.hp / s.max_hp) * 100));
    $("sHpFill").style.width = pct + "%";
  }
  const cond = $("sCond");
  if (Array.isArray(s.conditions) && s.conditions.length) {
    cond.innerHTML = s.conditions.map((c) => `<span class="chip">${escapeHtml(String(c))}</span>`).join("");
  } else {
    cond.innerHTML = `<span class="muted">ปกติ</span>`;
  }
  if (s.alive === false) {
    $("sName").innerHTML = escapeHtml(s.name || "") + " ☠";
  }
}

/* ---------- เรียก API ---------- */
async function callGM() {
  if (busy) return;
  busy = true;
  $("sendBtn").disabled = true;
  $("typing").hidden = false;
  chat.scrollTop = chat.scrollHeight;
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: history }),
    });
    const data = await res.json();
    if (!res.ok || data.error) {
      bubble("sys", "⚠️ " + (data.error || ("HTTP " + res.status)));
    } else {
      history.push({ role: "model", text: data.text });
      const { clean, state } = parseState(data.text);
      bubble("gm", clean || "…");
      if (state) updatePanel(state);
      save();
    }
  } catch (e) {
    bubble("sys", "⚠️ เชื่อมต่อเซิร์ฟเวอร์ไม่ได้: " + e.message);
  } finally {
    busy = false;
    $("sendBtn").disabled = false;
    $("typing").hidden = true;
    chat.scrollTop = chat.scrollHeight;
  }
}

function sendUser(text, displayKind = "you") {
  if (!text.trim() || busy) return;
  history.push({ role: "user", text });
  if (displayKind) bubble(displayKind, text);
  save();
  callGM();
}

/* ---------- เริ่มเกม ---------- */
function kickoff() {
  const { hero, klass, mode } = pick;
  let msg;
  if (mode === "C") {
    msg = `เริ่มเกมโหมด C ใช้ฮีโร่ "${hero}" (${klass}) โดยคุณ(AI)สวมบทฮีโร่และคิดเองด้วย เล่นทั้ง [GM] และ [ฮีโร่] ` +
      `จัดชีตระดับ 1 ตามหมวด ๓ แล้วเปิดฉาก "ถนนเถ้า" เดินเรื่อง 1 จังหวะแล้วหยุดให้ฉันกำกับ ` +
      `ฮีโร่ต้องไม่รู้ความจริงเบื้องหลังหรือค่าพลังศัตรู และอย่าลืมแนบบล็อก [[STATE]] ท้ายคำตอบ`;
  } else {
    msg = `เริ่มเกมโหมด A ฉันขอเล่นเป็นฮีโร่ "${hero}" (${klass}) ด้วยตัวเอง ` +
      `จัดชีตระดับ 1 ตามหมวด ๓ แล้วเปิดฉาก "ถนนเถ้า" จบด้วยการถามว่าฉันจะทำอะไร และอย่าลืมแนบบล็อก [[STATE]] ท้ายคำตอบ`;
  }
  bubble("sys", `⚔️ เริ่มเกม · ฮีโร่ ${hero} (${klass}) · โหมด ${mode}`);
  history.push({ role: "user", text: msg });
  save();
  callGM();
}

/* ---------- ผูกอีเวนต์หน้าเลือก ---------- */
$("heroPick").addEventListener("click", (e) => {
  const b = e.target.closest(".hero"); if (!b) return;
  document.querySelectorAll(".hero").forEach((x) => x.classList.remove("sel"));
  b.classList.add("sel");
  pick.hero = b.dataset.hero; pick.klass = b.dataset.klass;
  $("startBtn").disabled = false;
  $("startBtn").textContent = `เริ่มเกมกับ ${pick.hero} ▶`;
});
$("modePick").addEventListener("click", (e) => {
  const b = e.target.closest(".mode"); if (!b) return;
  document.querySelectorAll(".mode").forEach((x) => x.classList.remove("sel"));
  b.classList.add("sel");
  pick.mode = b.dataset.mode;
  $("setupHint").textContent = pick.mode === "C"
    ? "โหมด C: นั่งดู AI เล่นเอง กดปุ่ม ‘▶ ต่อ’ เพื่อเดินเรื่อง หรือพิมพ์กำกับได้"
    : "โหมด A: พิมพ์สิ่งที่ตัวละครจะทำในแต่ละตา";
});
$("startBtn").addEventListener("click", () => {
  if (!pick.hero) return;
  started = true;
  $("setup").classList.add("hidden");
  applyModeUI();
  save();
  kickoff();
});

/* ---------- ปุ่มส่ง/ต่อ/รีเซ็ต ---------- */
function applyModeUI() {
  $("contBtn").hidden = pick.mode !== "C";
  $("sMode").textContent = pick.mode;
}
$("sendBtn").addEventListener("click", () => {
  const t = $("input").value; $("input").value = ""; autosize();
  sendUser(t);
});
$("contBtn").addEventListener("click", () => sendUser("(เดินเรื่องต่อ)", "sys"));
$("input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("sendBtn").click(); }
});
$("input").addEventListener("input", autosize);
function autosize() {
  const el = $("input"); el.style.height = "auto"; el.style.height = Math.min(160, el.scrollHeight) + "px";
}
$("resetBtn").addEventListener("click", () => {
  if (!confirm("ล้างเกมปัจจุบันและเริ่มใหม่?")) return;
  localStorage.removeItem(LS); location.reload();
});

/* ---------- ตรวจการเชื่อมต่อ ---------- */
async function checkHealth() {
  try {
    const r = await fetch("/api/health"); const d = await r.json();
    const c = $("conn");
    if (d.key_set) { c.className = "conn ok"; c.title = "เชื่อมต่อแล้ว · " + (d.active_model || d.models[0]); }
    else { c.className = "conn bad"; c.title = "ยังไม่ได้ตั้งค่า GEMINI_API_KEY บนเซิร์ฟเวอร์"; }
  } catch (e) { $("conn").className = "conn bad"; }
}

/* ---------- กู้คืนเกมเดิม ---------- */
function restore() {
  $("setup").classList.add("hidden");
  applyModeUI();
  history.forEach((m, i) => {
    if (m.role === "model") {
      const { clean } = parseState(m.text);
      bubble("gm", clean);
    } else {
      if (i === 0 && /เริ่มเกมโหมด/.test(m.text)) {
        bubble("sys", `⚔️ เริ่มเกม · ฮีโร่ ${pick.hero} (${pick.klass}) · โหมด ${pick.mode}`);
      } else if (m.text === "(เดินเรื่องต่อ)") {
        bubble("sys", "▶ เดินเรื่องต่อ");
      } else {
        bubble("you", m.text);
      }
    }
  });
  if (lastState) updatePanel(lastState);
}

/* ---------- บูต ---------- */
checkHealth();
if (load()) { restore(); }
