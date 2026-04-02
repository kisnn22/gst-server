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
    "databaseURL": "https://your-db.firebaseio.com/"
})

client = vision.ImageAnnotatorClient()

# ===== OCR =====
def extract_text(image_bytes):
    image = vision.Image(content=image_bytes)
    response = client.text_detection(image=image)
    texts = response.text_annotations
    return texts[0].description if texts else ""

# ===== BLUR =====
def is_blur(image_bytes):
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
    return cv2.Laplacian(img, cv2.CV_64F).var() < 50

# ===== GST =====
def find_gst(text):
    match = re.findall(r"\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d]", text)
    return match[0] if match else None

# ===== STRONG INVOICE CHECK 🔥
def is_invoice(text):
    text = text.lower()

    score = 0

    if "invoice" in text: score += 2
    if "bill" in text: score += 1
    if "gst" in text: score += 2
    if "tax" in text: score += 1
    if "total" in text: score += 1
    if "amount" in text: score += 1

    gst = find_gst(text)
    if gst:
        score += 3   # 🔥 biggest signal

    return score >= 3   # threshold

# ===== FAKE GST =====
def fake_gst(gst):
    return gst.startswith("00")

@app.route('/')
def home():
    return "🔥 GST AI SERVER RUNNING"

@app.route('/upload', methods=['POST'])
def upload():

    image = request.get_data()
    if not image:
        return jsonify({"status": "ERROR"})

    text = extract_text(image)

    print("OCR TEXT:\n", text)

    # BLUR
    if is_blur(image):
        return jsonify({"status": "BLUR"})

    # INVOICE CHECK
    if not is_invoice(text):
        return jsonify({"status": "NOT_INVOICE"})

    # GST
    gst = find_gst(text)
    if not gst:
        return jsonify({"status": "GST_MISSING"})

    # FAKE
    if fake_gst(gst):
        return jsonify({"status": "FAKE_GST"})

    # DUPLICATE
    ref = db.reference("GST_HISTORY")
    data = ref.get() or {}

    if gst in data:
        return jsonify({"status": "DUPLICATE_GST"})

    ref.child(gst).set({"ok": True})

    return jsonify({"status": "VALID_INVOICE", "gst": gst})

if __name__ == "__main__":
    app.run()
