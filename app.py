from flask import Flask, request, jsonify
from google.cloud import vision
import firebase_admin
from firebase_admin import credentials, db
import re
import cv2
import numpy as np

app = Flask(__name__)

# ===== FIREBASE =====
cred = credentials.Certificate("key.json")
firebase_admin.initialize_app(cred, {
    "databaseURL": "https://smart-gst-compliance-ae82d-default-rtdb.firebaseio.com"
})

# ===== VISION CLIENT =====
client = vision.ImageAnnotatorClient()

# ===== OCR =====
def extract_text(image_bytes):
    image = vision.Image(content=image_bytes)
    response = client.text_detection(image=image)
    texts = response.text_annotations

    if texts:
        return texts[0].description
    return ""

# ===== BLUR DETECTION =====
def is_blur(image_bytes):
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)

    if img is None:
        return True

    variance = cv2.Laplacian(img, cv2.CV_64F).var()
    print("BLUR SCORE:", variance)

    return variance < 40   # tuned

# ===== GST FINDER (STRONG) =====
def find_gst(text):
    matches = re.findall(r"\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]", text)
    return matches[0] if matches else None

# ===== INVOICE DETECTION (AI LEVEL) =====
def is_invoice(text):
    text = text.lower()

    keywords = [
        "invoice", "bill", "gst", "tax", "total",
        "amount", "invoice no", "invoice number"
    ]

    score = 0

    for word in keywords:
        if word in text:
            score += 1

    gst = find_gst(text)
    if gst:
        score += 5   # 🔥 strongest signal

    if len(text) > 80:
        score += 2

    print("INVOICE SCORE:", score)

    return score >= 4

# ===== FAKE GST =====
def fake_gst(gst):
    return gst.startswith("00")

# ===== HOME =====
@app.route('/')
def home():
    return "🔥 GST AI SERVER RUNNING"

# ===== MAIN API =====
@app.route('/upload', methods=['POST'])
def upload():

    image = request.get_data()

    if not image:
        return jsonify({"status": "ERROR"})

    print("\n===== NEW REQUEST =====")

    # ===== BLUR CHECK =====
    if is_blur(image):
        print("❌ BLUR DETECTED")
        return jsonify({"status": "BLUR"})

    # ===== OCR =====
    text = extract_text(image)

    print("\n===== OCR TEXT =====")
    print(text)
    print("====================")

    # ===== INVOICE CHECK =====
    if not is_invoice(text):
        print("❌ NOT INVOICE")
        return jsonify({"status": "NOT_INVOICE"})

    # ===== GST =====
    gst = find_gst(text)

    if not gst:
        print("❌ GST MISSING")
        return jsonify({"status": "GST_MISSING"})

    print("✅ GST FOUND:", gst)

    # ===== FAKE GST =====
    if fake_gst(gst):
        print("❌ FAKE GST")
        return jsonify({"status": "FAKE_GST"})

    # ===== DUPLICATE CHECK =====
    ref = db.reference("GST_HISTORY")
    data = ref.get() or {}

    if gst in data:
        print("⚠️ DUPLICATE GST")
        return jsonify({"status": "DUPLICATE_GST"})

    # ===== SAVE =====
    ref.child(gst).set({"valid": True})

    print("✅ VALID INVOICE")

    return jsonify({
        "status": "VALID_INVOICE",
        "gst": gst
    })

# ===== RUN =====
if __name__ == "__main__":
    app.run()
