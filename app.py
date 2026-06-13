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

# ลำดับโมเดลที่อยากใช้ (คุณภาพดี -> เสถียร/ว่างสูง) ตัว lite ช่วยกัน error 503
PREFERRED_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-flash-latest",
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash-lite",
]


def discover_models():
    """ถามรายชื่อโมเดลที่คีย์นี้ใช้ได้จริง (รองรับ generateContent)"""
    if not API_KEY:
        return []
    try:
        r = requests.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            headers={"x-goog-api-key": API_KEY}, timeout=15,
        )
        if r.status_code == 200:
            out = []
            for m in r.json().get("models", []):
                if "generateContent" in m.get("supportedGenerationMethods", []):
                    name = m.get("name", "").replace("models/", "")
                    if name:
                        out.append(name)
            return out
    except Exception:
        pass
    return []


def build_candidates():
    available = set(discover_models())
    env_m = os.environ.get("GEMINI_MODEL", "").strip()
    wanted = []
    for m in ([env_m] if env_m else []) + PREFERRED_MODELS:
        if m and m not in wanted and (not available or m in available):
            wanted.append(m)
    return wanted or ["gemini-2.5-flash", "gemini-2.0-flash"]


CANDIDATE_MODELS = build_candidates()
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


CORE_LORE = """========== โลกและเนื้อเรื่อง: เงาเหนือมอร์นโฮลโลว์ (ย่อ) ==========
ฉาก: เมืองชายแดน 'มอร์นโฮลโลว์' ริมแดนเถ้า โทนมืดหม่น/โหด ฝนเถ้าโปรย หมอกพิษ ผู้คนหวาดกลัว
ตำนาน: 80 ปีก่อนเกิด 'เปลวร่วง (Emberfall)' ไฟปริศนาเผาเมืองเป็นเถ้า ทิ้งหมอกพิษและคนตายที่ไม่ยอมหลับ
[ความจริงลับ — GM เท่านั้น ห้ามบอกตรงๆ ให้ค้นพบเอง]: ใต้เมืองมี 'หัวใจเถ้า' แกนของเปลวร่วงที่ยังเต้น ดูดความตายไว้ (ศพเลยไม่หลับ)
  วายร้าย 'มารดาเถ้า' ผู้นำลัทธิเปลวเงา จะทำพิธีปลุกมันอีกครั้งโดยใช้คนหาย(คนงานเหมือง)เป็นเครื่องสังเวย ถ้าสำเร็จ = เปลวร่วงครั้งที่ 2 เผาทั้งแดน

สถานที่: ประตูแขวน(ศพโจรแขวนเตือน) · โรงเตี๊ยม 'ตะเกียงสุดท้าย'(ศูนย์ข่าว) · วิหารมารดาซีด(เทพีความตาย) · ร้านค้าบริษัท(รังแก๊ง) · เหมืองซินเดอร์โฮล(ทางลงใต้ดิน) · สุสานจม(ศพหาย) · ร้านยาอีฟรา
NPC (แต่ละตัวมีน้ำเสียง/วาระต่างกัน ให้คุยโต้ตอบกันเองด้วย):
- บรีดา: เจ้าของโรงเตี๊ยม ปากร้ายใจดี ลูกชายหายในเหมือง
- นายอำเภอเฮลกา: กฎหมายที่เหลือ ซื่อแต่สิ้นหวัง อยากกวาดล้างแก๊ง (พันธมิตร/ผู้มอบภารกิจ)
- การ์เร็ตต์ หน้ากากเหล็ก: หัวหน้าแก๊งคุมเมือง โหดแต่กลัวสิ่งใต้ดิน รีบกอบโกยจะหนี
- บาทหลวงคอร์วิน: นักบวชตาบอด รู้เรื่องคนตายไม่หลับ อดีตเคยเป็นสาวกลัทธิ
- อีฟรา: คนปรุงยา สายลับลัทธิแอบชี้เป้าเหยื่อ
- เกรน: คนขุดแร่รอดชีวิต เพ้อเรื่อง 'ไฟหายใจได้' (เบาะแสหลัก)
- ซิลดา: เด็กกำพร้ารู้ทางลับ (เดิมพันทางใจ ลัทธิหมายตา)
- มารดาเถ้า: วายร้ายในวิหารใต้พิภพ
กลุ่ม+นาฬิกาภัย: แก๊งหน้ากากเหล็ก(รีดไถจะหนี) / ลัทธิเปลวเงา(พิธี 6 ขีด เต็ม=หายนะ) / ผู้พิทักษ์(เฮลกา) / ชาวเมืองหวาดกลัว
  เดินนาฬิกาลัทธิ +1 เมื่อผู้เล่นพักยาว/ชักช้า ครบ 6 = พิธีเริ่มเอง

ฉากเปิด 'ถนนเถ้า': ผู้เล่นเดินทางมาถึง เจอขบวนถูกซุ่มโจมตีในหมอก สาวกลัทธิ+ผีดิบเถ้ากำลังลากคน(เหยื่อ)เข้าหมอก เหยื่อร้องขอชีวิต — สถานการณ์เปิด (สู้/ลอบ/ช่วย/เจรจา/สะกดรอย)
อาร์ค: สืบคนหายไปเหมือง / แก๊งไปทางลับ / คนตายไม่หลับไปวิหาร แล้วลงใต้ดิน(ฮอลโลว์เก่า): ปล่องเหมือง > ตลาดจม > คุกขังเหยื่อ > ลานสวด > ห้องหัวใจเถ้า(บอส)
  บอสฟื้น HP 15 ทุกเทิร์นตราบหัวใจเถ้ายังเต้น ต้องทำลาย/ดับหัวใจก่อน (เบาะแสในห้องลับ)
ตอนจบหลายแบบ: หยุดพิธีทัน=เมืองรอด(บอบช้ำ) / มาช้า=เปลวร่วงปะทุ หนีเอาชีวิต / เจรจารับอมตะ=ตกเป็นพวก / ใช้พันธมิตรช่วยรบ
เปิดทางกว้าง: ทุกปัญหาแก้ได้หลายทาง รับไอเดียนอกกรอบ ตั้ง DC ตามความยาก

ศัตรู(ค่าคร่าว): สาวกลัทธิ(AC12 HP9) · ผู้คลั่งลัทธิ(AC13 HP33 ร่ายเวท) · โจรหน้ากากเหล็ก(AC12 HP11) · การ์เร็ตต์(AC15 HP65) · ผีดิบเถ้า(AC12 HP22 กรงเล็บทำอัมพาต) · โครงกระดูก · ซอมบี้ · เงามรณะ · เอ็มเบอร์สพอว์น(ไฟ) · มารดาเถ้า(บอส AC15 HP75 เวทไฟ ลมหายใจเปลว ฟื้น15/เทิร์น)

ฮีโร่สำเร็จรูป 5 แบบ (lv1) — ใส่สกิล/ไอเท็มของตัวที่เลือกลงใน STATE:
- เคย์น: Human Fighter AC19 HP12 · ดาบยาว+5(1d8+3) Second Wind · อดีตทหารหนีอดีต
- เวสเปอร์: Tiefling Rogue AC15 HP9 · ดาบสั้น/ธนู+5 Sneak Attack 1d6 ลอบเร้น ต้านไฟ
- เอลส์เบธ: Human Cleric AC18 HP10 · เวท WIS DC13 Cure Wounds/Bless/Guiding Bolt/Sacred Flame · นักบวชมารดาซีด
- เรเวน: Human Ranger AC15 HP13 · ธนูยาว+5(1d8+3) Hunter's Mark Cure Wounds · นักล่าค่าหัว
- มอร์ดิไค: Human Wizard AC11(13 Mage Armor) HP8 เปราะ · เวท INT DC13 Fire Bolt+5(1d10) Magic Missile/Shield/Sleep · นักเวทนอกรีต

กฎย่อ: d20+โมดิฟายเออร์ vs DC/AC · ได้เปรียบ=ทอย 2 เอาสูง · 20=คริติคอล · ใช้กฎ D&D 5e (2024) มาตรฐานเติมรายละเอียดได้ แต่ห้ามเปลี่ยนกฏเหล็ก"""

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

[[STATE]]{"name":"ชื่อฮีโร่","klass":"คลาส","level":1,"hp":12,"max_hp":12,"ac":19,"conditions":[],"location":"ถนนเถ้า","gold":10,"clock":"0/6","mode":"A","alive":true,"skills":[{"n":"Fire Bolt","d":"1d10 ไฟ 120ฟุต"},{"n":"Ray of Frost","d":"1d8 เย็น ลดสปีด"}],"items":[{"n":"ยาฟื้นพลัง","q":1},{"n":"ตำราเวท"}]}[[/STATE]]

กติกาบล็อกสถานะ: เป็น JSON ถูกต้องบรรทัดเดียว, ห้าม comment, ใส่ครั้งเดียวท้ายสุด, ห้ามครอบ code fence,
อัปเดตค่าทุกตัวให้ตรงสถานการณ์ปัจจุบัน (โดยเฉพาะ hp, conditions, location, clock) — clock คือนาฬิกาพิธีลัทธิรูปแบบ "x/6"
- skills = สกิล/คาถา/ความสามารถที่ฮีโร่ใช้ได้ตอนนี้ (คาถาเล็ก เวทเตรียม ความสามารถคลาส อาวุธหลัก) แต่ละตัว {"n":ชื่อสั้น,"d":คำอธิบายสั้นมาก} ใส่ 3-7 ตัวที่ใช้บ่อย
- items = ไอเท็มสำคัญที่พกอยู่ {"n":ชื่อ,"q":จำนวนถ้านับได้} — อัปเดตเมื่อใช้/ได้/หมด (เช่นดื่มยาแล้ว q ลด หรือเอาออก)
"""

SYSTEM_PROMPT = WEB_GM_INSTRUCTIONS + "\n\n" + CORE_LORE


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


OVERLOAD = (500, 502, 503, 504)


def call_gemini(contents):
    models = list(CANDIDATE_MODELS)
    if _state["model"] and _state["model"] in models:
        models.remove(_state["model"])
        models.insert(0, _state["model"])
    last_err = "ไม่มีโมเดลให้ลอง"
    quota_hit = False
    for attempt in range(2):  # วนซ้ำเฉพาะกรณีโมเดลโหลดสูงชั่วคราว (5xx) เท่านั้น
        saw_overload = False
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
                saw_overload = True
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
            last_err = "HTTP %s (%s): %s" % (r.status_code, model, r.text[:140])
            if r.status_code == 429:
                quota_hit = True
                continue  # โควต้าเต็ม → ลองโมเดลถัดไป 'ครั้งเดียว' ไม่วนรัวๆ ให้เปลืองโควต้า
            if r.status_code in OVERLOAD:
                saw_overload = True
                continue  # โหลดสูงชั่วคราว → ลองโมเดลถัดไป
            if r.status_code in (400, 404):
                continue  # โมเดลใช้ไม่ได้ → ลองตัวถัดไป
            return None, model, last_err  # เช่น 401/403 คีย์ผิด → หยุด
        if not saw_overload:
            break  # ไม่ใช่ overload (เช่นโควต้าเต็ม) ไม่ต้องวนซ้ำให้เปลือง
        time.sleep(1.5)
    if quota_hit:
        return None, None, ("โควต้า Gemini ฟรีเต็มชั่วคราว (429) — รอสัก 1 นาทีแล้วกด 'ลองอีกครั้ง' "
                            "หรือเปิด billing ใน Google AI Studio เพื่อเล่นต่อเนื่อง")
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
        "module_chars": len(SYSTEM_PROMPT),
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
