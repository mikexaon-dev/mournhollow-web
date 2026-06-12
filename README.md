# เงาเหนือมอร์นโฮลโลว์ — เว็บเล่น D&D โทนมืดกับ AI

เว็บแอปเล่นบทผจญภัย D&D โทนมืดผ่าน Chrome โดยมี **Gemini เป็น Game Master**
มีหน้าแชตแสดงสถานการณ์ · ช่องพิมพ์สิ่งที่ตัวละครจะทำ · และแผงสถานะ (HP / เงื่อนไข / ฉาก / นาฬิกาพิธีลัทธิ) อัปเดตสด

> กลไกกฎจาก D&D SRD 5.2 (CC BY 4.0) · เนื้อเรื่อง/เมือง/ตัวละครเป็นงานต้นฉบับ

---

## โครงสร้างไฟล์
```
mournhollow-web/
├─ app.py            # เซิร์ฟเวอร์ Flask (เสิร์ฟหน้าเว็บ + พร็อกซีเรียก Gemini)
├─ module.html       # เนื้อโมดูลเต็ม (ใช้เป็น system prompt ของ GM)
├─ static/           # หน้าเว็บ (index.html, style.css, app.js)
├─ requirements.txt  # ไลบรารี Python
├─ render.yaml       # ค่า deploy สำหรับ Render (Blueprint)
├─ Procfile          # คำสั่งสตาร์ทสำรอง
└─ .env.example      # ตัวอย่างตัวแปรลับ
```

## 🔑 ขอ Gemini API Key (ฟรี)
1. ไปที่ **https://aistudio.google.com/apikey**
2. กด *Create API key* แล้วคัดลอกไว้ (ขึ้นต้นด้วย `AIza...`)

---

## 🖥️ รันในเครื่อง (ทดสอบก่อน deploy)
```powershell
cd mournhollow-web
pip install -r requirements.txt
$env:GEMINI_API_KEY = "วางคีย์ของคุณที่นี่"
python app.py
```
เปิด Chrome ไปที่ **http://localhost:5000** แล้วเลือกฮีโร่ + โหมด → เริ่มเล่น

---

## ☁️ Deploy ขึ้น Render ผ่าน GitHub (เล่นจากที่ไหนก็ได้)

### ขั้นที่ 1 — ดันโค้ดขึ้น GitHub
สร้าง repo เปล่าบน GitHub (เช่นชื่อ `mournhollow-web`) แล้วในโฟลเดอร์นี้:
```powershell
git init
git add .
git commit -m "Mournhollow web game"
git branch -M main
git remote add origin https://github.com/<ชื่อคุณ>/mournhollow-web.git
git push -u origin main
```

### ขั้นที่ 2 — เชื่อม Render กับ GitHub
1. เข้า **https://render.com** → สมัคร/ล็อกอินด้วย GitHub
2. กด **New +** → **Blueprint**
3. เลือก repo `mournhollow-web` → Render จะอ่าน `render.yaml` ให้อัตโนมัติ
4. กด **Apply** เพื่อสร้างเซอร์วิส

> ถ้าไม่อยากใช้ Blueprint: New + → **Web Service** → เลือก repo →
> Build = `pip install -r requirements.txt` · Start = `gunicorn app:app --bind 0.0.0.0:$PORT --timeout 120`

### ขั้นที่ 3 — ใส่คีย์ลับใน Render
ในหน้าเซอร์วิส → **Environment** → เพิ่ม:

| Key | Value |
|-----|-------|
| `GEMINI_API_KEY` | คีย์ที่ขอมา (ห้ามใส่ในโค้ด) |
| `GEMINI_MODEL` | `gemini-2.5-flash` (ปรับได้) |

กด **Save** → Render จะ deploy ให้ ได้ URL เช่น `https://mournhollow.onrender.com` → เปิดใน Chrome เล่นได้เลย

### อัปเดตเกมภายหลัง
แก้โค้ดแล้ว `git push` — Render จะ deploy เวอร์ชันใหม่ให้อัตโนมัติ

---

## ⚙️ ตัวแปรสภาพแวดล้อม
| ตัวแปร | ค่าเริ่มต้น | คำอธิบาย |
|--------|-----------|----------|
| `GEMINI_API_KEY` | (จำเป็น) | คีย์ Gemini — เก็บฝั่งเซิร์ฟเวอร์เท่านั้น ไม่หลุดถึงเบราว์เซอร์ |
| `GEMINI_MODEL` | `gemini-2.5-flash` | ถ้าโมเดลใช้ไม่ได้ ระบบจะลอง `gemini-2.0-flash` และ `gemini-1.5-flash` ให้เอง |
| `PORT` | `5000` (local) | Render ตั้งให้อัตโนมัติ |

## 🩹 แก้ปัญหาที่พบบ่อย
- **จุดสถานะมุมขวาเป็นสีแดง / ขึ้น “ยังไม่ได้ตั้งค่า GEMINI_API_KEY”** → ยังไม่ได้ใส่คีย์ใน Render (หรือ `$env:` ในเครื่อง)
- **ขึ้น HTTP 404 จากทุกโมเดล** → เปลี่ยน `GEMINI_MODEL` เป็นชื่อที่บัญชีคุณมีสิทธิ์ (ดูที่ AI Studio)
- **ครั้งแรกโหลดช้า** → Render free จะ “หลับ” เมื่อไม่มีคนใช้ ตื่นครั้งแรกใช้เวลาราว 30–60 วิ
- **GM ไม่ตอบ / ถูกบล็อก** → ลองพิมพ์ใหม่; เนื้อหารุนแรงเกินไปอาจโดนตัวกรอง Gemini (เราตั้ง threshold ต่ำสุดที่อนุญาตแล้ว)

## 🔒 ความปลอดภัย
คีย์ API อยู่ฝั่งเซิร์ฟเวอร์ (`app.py` อ่านจาก env) เบราว์เซอร์เรียกผ่าน `/api/chat` เท่านั้น
ไฟล์ `.env` ถูกกันไว้ใน `.gitignore` แล้ว — อย่า commit คีย์จริงขึ้น GitHub
