from flask import Flask, request, jsonify
from google.cloud import vision
import firebase_admin
from firebase_admin import credentials, db
import numpy as np
import cv2
import re
import datetime
import os

app = Flask(__name__)

# ================= GOOGLE VISION =================
client = vision.ImageAnnotatorClient()

# ================= FIREBASE =================
cred = credentials.Certificate("key.json")
firebase_admin.initialize_app(cred, {
    "databaseURL": "https://YOUR_DB.firebaseio.com/"
})

print("🔥 Firebase Connected")

# ================= GST REGEX =================
gst_pattern = r"\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d]"

# ================= BLUR CHECK =================
def is_blur(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    value = cv2.Laplacian(gray, cv2.CV_64F).var()
    print("🔍 Blur Value:", value)
    return value < 80

# ================= OCR =================
def extract_text(image_bytes):
    image = vision.Image(content=image_bytes)
    response = client.text_detection(image=image)
    texts = response.text_annotations

    if texts:
        return texts[0].description
    return ""

# ================= INVOICE CHECK =================
def is_invoice(text):
    keywords = ["invoice", "bill", "gst", "tax"]
    return any(k in text.lower() for k in keywords)

# ================= ROUTES =================
@app.route('/')
def home():
    return "🚀 GST AI Server Running"

@app.route('/upload', methods=['POST'])
def upload():

    try:
        print("\n🔥 ===== NEW REQUEST =====")

        image_bytes = request.get_data()

        if not image_bytes:
            return jsonify({"status": "error", "msg": "no image"})

        # ===== IMAGE DECODE =====
        npimg = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(npimg, cv2.IMREAD_COLOR)

        # ===== BLUR CHECK =====
        if is_blur(img):
            print("⚠ Image Blur")
            return jsonify({"status": "BLUR"})

        # ===== OCR =====
        text = extract_text(image_bytes)
        print("🧠 OCR TEXT:\n", text)

        # ===== INVOICE CHECK =====
        if not is_invoice(text):
            print("❌ Not Invoice")
            return jsonify({"status": "NOT_INVOICE"})

        # ===== GST FIND =====
        gst_list = re.findall(gst_pattern, text)

        if not gst_list:
            print("❌ GST Missing")
            return jsonify({"status": "GST_MISSING"})

        gst = gst_list[0]
        print("✅ GST Found:", gst)

        # ===== DUPLICATE CHECK =====
        ref = db.reference("GST_History")
        data = ref.get()

        if data:
            for key in data:
                if data[key]["gst"] == gst:
                    print("⚠ Duplicate GST")
                    return jsonify({"status": "DUPLICATE", "gst": gst})

        # ===== SAVE TO FIREBASE =====
        new_data = {
            "gst": gst,
            "text": text,
            "time": str(datetime.datetime.now()),
            "status": "valid"
        }

        ref.push(new_data)
        print("🔥 Saved to Firebase")

        return jsonify({
            "status": "VALID_INVOICE",
            "gst": gst
        })

    except Exception as e:
        print("❌ ERROR:", e)
        return jsonify({"status": "error", "msg": str(e)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
