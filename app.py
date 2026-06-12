"""
เงาเหนือมอร์นโฮลโลว์ — เว็บเซิร์ฟเวอร์เกม D&D โทนมืด
Backend แบบบาง: เสิร์ฟหน้าเว็บ + พร็อกซีเรียก Gemini เป็น Game Master/นักเล่าเรื่อง
คีย์ API เก็บฝั่งเซิร์ฟเวอร์เท่านั้น (ตั้งผ่าน environment variable บน Render)
"""
import os
import re
import html
import json
import time
import requests
from flask import Flask, request, jsonify, send_from_directory

BASE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder="static", static_url_path="")

API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

CANDIDATE_MODELS = []
for _m in [os.environ.get("GEMINI_MODEL", "").strip(),
           "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
    if _m and _m not in CANDIDATE_MODELS:
        CANDIDATE_MODELS.append(_m)

_state = {"model": None}


def html_to_text(path):
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

WEB_GM_INSTRUCTIONS = """คุณคือ "Game Master" และนักเล่าเรื่องของเกม D&D โทนมืดชื่อ "เงาเหนือมอร์นโฮลโลว์"
เล่นผ่านหน้าเว็บแชต ทำตามโมดูลเต็ม (อยู่ท้ายข้อความนี้) และ "กฏเหล็ก" ทุกข้ออย่างเคร่งครัด

✦ สไตล์การเล่า — ทำให้รู้สึกเหมือนกำลังอ่านนิยายที่สนุกและอ่านง่าย:
1. เล่าเป็นร้อยแก้วลื่นไหล ใช้ภาษาเรียบง่าย ชัดเจน เห็นภาพ ไม่ใช้คำยากหรือประโยควกวน
   อธิบายสถานการณ์ให้ผู้เล่นเข้าใจทันทีว่ากำลังเกิดอะไรขึ้น เห็นอะไร ได้ยินอะไร รู้สึกอย่างไร
2. ใส่ "บทสนทนา" ของตัวละครให้เป็นธรรมชาติ แต่ละตัวมีน้ำเสียง นิสัย และวิธีพูดต่างกันชัดเจน
   เขียนบทพูดรูปแบบนี้เป๊ะ ๆ (ชื่อ ตามด้วยโคลอน เว้นวรรค แล้วคำพูดในเครื่องหมายคำพูด) ขึ้นบรรทัดใหม่ทุกครั้งที่มีคนพูด เช่น
     บรีดา: "เจ้าหน้าใหม่อีกคนสินะ... หวังว่าจะอยู่นานกว่าคนก่อนนะ"
     นายอำเภอเฮลกา: "อย่าไปฟังยายแก่นั่น คนแปลกหน้า เมืองนี้ยังพอมีคนซื่ออยู่บ้าง"
3. ให้ NPC "มีปฏิสัมพันธ์กันเอง" ไม่ใช่รอแต่ผู้เล่น — พวกเขาคุยกัน เถียงกัน หยอกล้อ ขัดคอ หรือช่วยเหลือกัน
   ทำให้ทุกฉากรู้สึกเหมือนมีคนจริง ๆ มีชีวิตอยู่ในนั้น มีอารมณ์และความสัมพันธ์ต่อกัน
4. กระชับพอดีอ่านในแชต (ราว 5–12 บรรทัด) ผสมการบรรยายกับบทพูดให้พอดี จบแต่ละตอนด้วยจังหวะที่ชวนให้อยากเล่นต่อ
   ในโหมด A ปิดท้ายด้วยคำถามทำนอง "คุณจะทำอะไร?" (เนียน ๆ ไม่ใช่เมนูตัวเลือก)
5. เขียนสดใหม่ทุกครั้ง อย่าใช้ประโยคหรือคำบรรยายซ้ำเดิม รักษาอารมณ์ ความตื่นเต้น และโทนมืดของเรื่องไว้เสมอ

✦ กติกาเกม (ยึดกฏเหล็ก):
6. ทอยลูกเต๋าจริงและสุ่มอย่างไม่ลำเอียง สอดผลและการคำนวณเข้าไปในเนื้อเรื่องอย่างแนบเนียน
   เช่น (ทอย d20: 14 +3 = 17 ปะทะ AC 15) — แล้วเล่าต่อว่าดาบเฉือนเข้าที่ไหล่ของมัน
   ห้ามแก้ผลย้อนหลัง ห้ามเข้าข้างผู้เล่น ตัวละครบาดเจ็บและตายได้จริง
   หากผู้เล่นแจ้งผลทอยมาเอง (ข้อความขึ้นต้น "(ผลทอยของฉัน:") ให้ยอมรับว่าซื่อตรงและใช้ตัดสิน ส่วนเต๋าศัตรู/ค่าซ่อน (DC) คุณทอยเอง
7. ผู้เล่นพิมพ์ "สิ่งที่ตัวละครพยายามทำ" คุณเป็นผู้ตัดสินผลด้วยกฎ+เต๋า อย่าตัดสินใจแทนผู้เล่น
8. เคารพ "โหมด": A = ผู้เล่นคุมฮีโร่ · B/C = คุณสวมบทฮีโร่และคิดเองด้วย (ฮีโร่ต้องไม่รู้ความจริงเบื้องหลังหรือค่าพลังศัตรู)
9. เริ่มเกม: จัดฮีโร่ตามที่เลือก (หมวด ๓ มี 5 แบบ) แล้วเปิดด้วยฉาก "ถนนเถ้า" (หมวด ๕.๒)

✦ บล็อกสถานะ (สำคัญมาก): ที่ "ท้ายสุด" ของทุกคำตอบ แนบสถานะหนึ่งบรรทัดรูปแบบนี้เป๊ะ ๆ
(แอปจะดึงไปแสดงบนแผงสถานะ และจะไม่โชว์บล็อกนี้ให้ผู้เล่นเห็น):

[[STATE]]{"name":"ชื่อฮีโร่","klass":"คลาส","level":1,"hp":12,"max_hp":12,"ac":19,"conditions":[],"location":"ถนนเถ้า","gold":10,"clock":"0/6","mode":"A","alive":true}[[/STATE]]

กติกาบล็อกสถานะ: เป็น JSON ถูกต้องบรรทัดเดียว, ห้าม comment, ใส่ครั้งเดียวท้ายสุด, ห้ามครอบ code fence,
อัปเดตค่าทุกตัวให้ตรงสถานการณ์ปัจจุบัน (โดยเฉพาะ hp, conditions, location, clock) — clock คือนาฬิกาพิธีลัทธิรูปแบบ "x/6"
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
            "maxOutputTokens": 4096,
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
        ],
    }


TRANSIENT = (429, 500, 502, 503, 504)


def call_gemini(contents):
    models = list(CANDIDATE_MODELS)
    if _state["model"] and _state["model"] in models:
        models.remove(_state["model"])
        models.insert(0, _state["model"])
    last_err = "ไม่มีโมเดลให้ลอง"
    for attempt in range(2):  # ลองซ้ำ 1 รอบถ้าทุกโมเดลโหลดสูงชั่วคราว
        saw_transient = False
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
                last_err = "หมดเวลาเชื่อมต่อ Gemini (timeout)"
                saw_transient = True
                continue
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
                    return None, model, "โมเดลไม่ส่งข้อความ (finishReason=%s) อาจถูกตัวกรองบล็อก ลองพิมพ์ใหม่" % reason
                pf = data.get("promptFeedback", {})
                return None, model, "ถูกบล็อก: %s" % json.dumps(pf, ensure_ascii=False)[:300]
            last_err = "HTTP %s (%s): %s" % (r.status_code, model, r.text[:160])
            if r.status_code in TRANSIENT:
                saw_transient = True
                continue  # โมเดลโหลดสูง/ชั่วคราว → ลองโมเดลถัดไปทันที
            if r.status_code in (400, 404):
                continue  # โมเดลใช้ไม่ได้ → ลองโมเดลถัดไป
            return None, model, last_err  # เช่น 401/403 คีย์ผิด → หยุด
        if not saw_transient:
            break
        time.sleep(1.5)  # ทุกโมเดลโหลดสูง รอแล้วลองทั้งชุดอีกครั้ง
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
