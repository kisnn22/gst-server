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
    "databaseURL": "https://your-project-id-default-rtdb.firebaseio.com/"
})

# ===== VISION =====
client = vision.ImageAnnotatorClient()

# ===== OCR =====
def extract_text(img):
    image = vision.Image(content=img)
    res = client.text_detection(image=image)
    texts = res.text_annotations
    return texts[0].description if texts else ""

# ===== IMAGE QUALITY AI =====
def image_quality_score(img):
    arr = np.frombuffer(img, np.uint8)
    im = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)

    if im is None:
        return 0

    blur = cv2.Laplacian(im, cv2.CV_64F).var()
    edges = cv2.Canny(im, 50, 150).sum()

    score = (blur * 0.6) + (edges * 0.0001)

    print("QUALITY SCORE:", score)

    return score

# ===== GST DETECTION =====
def find_gst(text):
    matches = re.findall(r"\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]", text)
    return matches[0] if matches else None

# ===== AI INVOICE DETECTION =====
def invoice_confidence(text):
    text = text.lower()

    keywords = ["invoice","bill","gst","tax","amount","total"]
    score = sum([1 for k in keywords if k in text])

    if find_gst(text):
        score += 5

    if len(text) > 80:
        score += 2

    return score

# ===== FAKE GST CHECK =====
def fake_gst(gst):
    return gst.startswith("00")

@app.route('/')
def home():
    return "🔥 AI GST SERVER LIVE"

@app.route('/upload', methods=['POST'])
def upload():
    try:
        img = request.get_data()

        if not img:
            return jsonify({"status":"ERROR"})

        # 🔹 STEP 1: IMAGE QUALITY
        quality = image_quality_score(img)

        if quality < 50:
            return jsonify({"status":"LOW_QUALITY"})

        # 🔹 STEP 2: OCR
        text = extract_text(img)

        print("\nOCR:\n", text)

        # 🔹 STEP 3: AI CONFIDENCE
        conf = invoice_confidence(text)

        print("CONFIDENCE:", conf)

        if conf < 5:
            return jsonify({"status":"NOT_INVOICE"})

        # 🔹 STEP 4: GST
        gst = find_gst(text)

        if not gst:
            return jsonify({"status":"GST_MISSING"})

        # 🔹 STEP 5: FAKE GST
        if fake_gst(gst):
            return jsonify({"status":"FAKE_GST"})

        # 🔹 STEP 6: DUPLICATE
        ref = db.reference("GST_HISTORY")
        data = ref.get() or {}

        if gst in data:
            return jsonify({"status":"DUPLICATE_GST"})

        ref.child(gst).set({"valid":True})

        return jsonify({
            "status":"VALID_INVOICE",
            "gst":gst,
            "confidence":conf
        })

    except Exception as e:
        print("ERROR:", e)
        return jsonify({"status":"ERROR"})
