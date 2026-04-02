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

# ===== VISION =====
client = vision.ImageAnnotatorClient()

# ===== OCR =====
def extract_text(image_bytes):
    image = vision.Image(content=image_bytes)
    response = client.text_detection(image=image)
    texts = response.text_annotations
    return texts[0].description if texts else ""

# ===== BLUR CHECK =====
def is_blur(image_bytes):
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
    score = cv2.Laplacian(img, cv2.CV_64F).var()
    return score < 50

# ===== INVOICE DETECTION =====
def invoice_confidence(text):
    keywords = ["invoice", "bill", "gst", "tax"]
    score = sum(1 for k in keywords if k in text.lower())
    return score / len(keywords)

# ===== GST FIND =====
def find_gst(text):
    match = re.findall(r"\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d]", text)
    return match[0] if match else None

# ===== FAKE GST CHECK =====
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

    # BLUR
    if is_blur(image):
        return jsonify({"status": "BLUR"})

    # INVOICE CONFIDENCE
    conf = invoice_confidence(text)
    if conf < 0.4:
        return jsonify({"status": "NOT_INVOICE", "confidence": conf})

    # GST
    gst = find_gst(text)
    if not gst:
        return jsonify({"status": "GST_MISSING"})

    # FAKE GST
    if fake_gst(gst):
        return jsonify({"status": "FAKE_GST"})

    # DUPLICATE CHECK
    ref = db.reference("GST_HISTORY")
    data = ref.get() or {}

    if gst in data:
        return jsonify({"status": "DUPLICATE_GST", "gst": gst})

    ref.child(gst).set({"detected": True})

    return jsonify({
        "status": "VALID_INVOICE",
        "gst": gst,
        "confidence": conf
    })

if __name__ == "__main__":
    app.run()
