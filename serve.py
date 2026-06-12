"""ตัวรันเซิร์ฟเวอร์แบบ detached สำหรับเล่นในเครื่อง (ใช้ Flask dev server)"""
import os
import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
