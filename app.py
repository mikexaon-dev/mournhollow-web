"""
เงาเหนือมอร์นโฮลโลว์ — เว็บเซิร์ฟเวอร์เกม D&D โทนมืด
Backend แบบบาง: เสิร์ฟหน้าเว็บ + พร็อกซีเรียก Gemini เป็น Game Master
คีย์ API เก็บฝั่งเซิร์ฟเวอร์เท่านั้น (ตั้งผ่าน environment variable บน Render)
"""
import os
import re
import html
import json
import requests
from flask import Flask, request, jsonify, send_from_directory

BASE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder="static", static_url_path="")

API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

# ลำดับโมเดลที่จะลอง (env มาก่อน แล้วค่อย fallback) — กันชื่อโมเดลเปลี่ยน
CANDIDATE_MODELS = []
for _m in [os.environ.get("GEMINI_MODEL", "").strip(),
           "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
    if _m and _m not in CANDIDATE_MODELS:
        CANDIDATE_MODELS.append(_m)

_state = {"model": None}  # จำโมเดลที่ใช้งานได้สำเร็จล่าสุด


def html_to_text(path):
    """แปลง module.html เป็นข้อความล้วนสำหรับใช้เป็น system prompt ของ GM"""
    try:
        src = open(path, encoding="utf-8").read()
    except OSError:
        return ""
    src = re.sub(r"<head.*?</head>", "", src, flags=re.S | re.I)
    src = re.sub(r"<style.*?</style>", "", src, flags=re.S | re.I)
    src = re.sub(r"<script.*?</script>", "", src, flags=re.S | re.I)
    src = re.sub(r"<li[^>]*>", "\n- ", src, flags=re.I)
    src = re.sub(r"<(th|td)[^>]*>", " | ", src, flags=re.I)
    src = re.sub(r"<(br|/p|/li|/tr|/h[1-4]|/div|/table|/section)\s*>", "\n", src, flags=re.I)
    text = re.sub(r"<[^>]+>", "", src)
    text = html.unescape(text)
    text = "\n".join(line.rstrip() for line in text.splitlines())
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


MODULE_TEXT = html_to_text(os.path.join(BASE, "module.html"))

WEB_GM_INSTRUCTIONS = """คุณคือ "Game Master" ของเกมเล่นตามบทบาท D&D โทนมืดชื่อ "เงาเหนือมอร์นโฮลโลว์"
ที่เล่นผ่านหน้าเว็บแชต ทำตามโมดูลเต็ม (อยู่ท้ายข้อความนี้) และ "กฏเหล็ก" ทุกข้ออย่างเคร่งครัด

หลักปฏิบัติสำหรับเวอร์ชันเว็บ:
1. บรรยายเป็นภาษาไทย โทนมืดหม่น/โหด กระชับพอดีแชต (ราว 4–10 บรรทัด) อย่าร่ายยาวเป็นนิยาย
2. ทอยลูกเต๋าจริงและสุ่มอย่างไม่ลำเอียง แสดงการคำนวณในบรรทัด เช่น (d20: 14 +3 = 17 vs AC 15 → โดน)
   ห้ามแก้ผลย้อนหลัง ห้ามเข้าข้างผู้เล่น ตัวละครบาดเจ็บและตายได้จริง
3. ผู้เล่นพิมพ์ "สิ่งที่ตัวละครพยายามทำ" คุณเป็นผู้ตัดสินผลด้วยกฎ+เต๋า อย่าตัดสินใจแทนผู้เล่น
   เมื่อถึงทางเลือกของตัวละคร ให้จบด้วยคำถามทำนอง "คุณจะทำอะไร?"
4. เคารพ "โหมด" ที่ผู้เล่นเลือก (จะแจ้งในข้อความแรก):
   - โหมด A: ผู้เล่น(มนุษย์)คุมฮีโร่
   - โหมด B/C: คุณ(AI)สวมบทฮีโร่และคิดเองด้วย (ทำตามหมวด ๑·๕) โดยฮีโร่ต้องไม่รู้ความจริงเบื้องหลัง/ค่าพลังศัตรู
5. เมื่อเริ่มเกม: จัดฮีโร่ตามที่เลือก (หมวด ๓) แล้วเปิดด้วยฉาก "ถนนเถ้า" (หมวด ๕.๒)

**สำคัญมาก — บล็อกสถานะ:** ที่ "ท้ายสุด" ของทุกคำตอบ ให้แนบสถานะเกมหนึ่งบรรทัดในรูปแบบนี้เป๊ะ ๆ
(แอปจะดึงไปแสดงบนแผงสถานะ และจะไม่โชว์บล็อกนี้ให้ผู้เล่นเห็น):

[[STATE]]{"name":"ชื่อฮีโร่","klass":"คลาส","level":1,"hp":12,"max_hp":12,"ac":19,"conditions":[],"location":"ถนนเถ้า","gold":10,"clock":"0/6","mode":"A","alive":true}[[/STATE]]

กติกาบล็อกสถานะ: ต้องเป็น JSON ถูกต้องบรรทัดเดียว, ห้ามใส่ comment, ใส่ครั้งเดียวที่ท้ายสุด,
ห้ามครอบด้วย code fence, อัปเดตค่าทุกตัวให้ตรงกับสถานการณ์ปัจจุบัน (โดยเฉพาะ hp, conditions, location, clock)
clock คือนาฬิกาพิธีลัทธิ รูปแบบ "x/6" เดินหน้าเมื่อผู้เล่นชักช้า/พักยาว
"""

SYSTEM_PROMPT = (
    WEB_GM_INSTRUCTIONS
    + "\n\n========== โมดูลเต็ม: เงาเหนือมอร์นโฮลโลว์ ==========\n\n"
    + MODULE_TEXT
)


def build_payload(contents):
    return {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.95,
            "topP": 0.95,
            "maxOutputTokens": 2048,
        },
        # โทน grimdark มีความรุนแรงแฟนตาซี ลดการบล็อกเกินจำเป็น
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
        ],
    }


def call_gemini(contents):
    """ลองเรียกโมเดลตามลำดับ คืน (text, model, error)"""
    models = list(CANDIDATE_MODELS)
    if _state["model"] and _state["model"] in models:
        models.remove(_state["model"])
        models.insert(0, _state["model"])
    last_err = "ไม่มีโมเดลให้ลอง"
    for model in models:
        url = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent" % model
        try:
            r = requests.post(
                url,
                headers={"x-goog-api-key": API_KEY, "Content-Type": "application/json"},
                json=build_payload(contents),
                timeout=120,
            )
        except requests.Timeout:
            return None, model, "หมดเวลาเชื่อมต่อ Gemini (timeout)"
        except Exception as e:  # noqa
            last_err = "เชื่อมต่อไม่ได้: %s" % e
            continue
        if r.status_code == 200:
            data = r.json()
            cands = data.get("candidates", [])
            if cands:
                parts = cands[0].get("content", {}).get("parts", [])
                text = "".join(p.get("text", "") for p in parts).strip()
                if text:
                    _state["model"] = model
                    return text, model, None
                reason = cands[0].get("finishReason", "")
                return None, model, "โมเดลไม่ส่งข้อความ (finishReason=%s) อาจถูกตัวกรองบล็อก" % reason
            pf = data.get("promptFeedback", {})
            return None, model, "ถูกบล็อก: %s" % json.dumps(pf, ensure_ascii=False)[:300]
        last_err = "HTTP %s จากโมเดล %s: %s" % (r.status_code, model, r.text[:200])
        if r.status_code in (400, 404):
            continue  # ลองโมเดลถัดไป
        break
    return None, None, last_err


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/health")
def health():
    return jsonify({
        "ok": True,
        "key_set": bool(API_KEY),
        "models": CANDIDATE_MODELS,
        "active_model": _state["model"],
        "module_chars": len(MODULE_TEXT),
    })


@app.route("/api/chat", methods=["POST"])
def chat():
    if not API_KEY:
        return jsonify({"error": "เซิร์ฟเวอร์ยังไม่ได้ตั้งค่า GEMINI_API_KEY"}), 503
    data = request.get_json(force=True, silent=True) or {}
    messages = data.get("messages", [])
    # กันประวัติยาวเกิน: เก็บ 50 ข้อความหลังสุด
    messages = messages[-50:]
    contents = []
    for m in messages:
        role = "model" if m.get("role") == "model" else "user"
        contents.append({"role": role, "parts": [{"text": str(m.get("text", ""))}]})
    if not contents:
        return jsonify({"error": "ไม่มีข้อความ"}), 400
    text, model, err = call_gemini(contents)
    if err:
        return jsonify({"error": err}), 502
    return jsonify({"text": text, "model": model})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
