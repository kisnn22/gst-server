from flask import Flask, request, jsonify
import cv2
import numpy as np
import re
from google.cloud import vision
import firebase_admin
from firebase_admin import credentials, db

app = Flask(__name__)

# FIREBASE
cred = credentials.Certificate("key.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'YOUR_FIREBASE_URL'
})

client = vision.ImageAnnotatorClient()

# GST REGEX
def find_gst(text):
    pattern = r"\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d][Z][A-Z\d]"
    match = re.search(pattern, text)
    return match.group() if match else None

# BLUR DETECTION
def is_blur(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var() < 100

# SMART INVOICE DETECTION
def is_invoice(text):
    keywords = ["invoice","bill","gst","total","tax","amount","qty"]
    score = sum(1 for k in keywords if k in text.lower())
    return score >= 2

# OCR
def extract_text(image_bytes):
    image = vision.Image(content=image_bytes)
    response = client.text_detection(image=image)
    texts = response.text_annotations
    return texts[0].description if texts else ""

@app.route('/upload', methods=['POST'])
def upload():
    try:
        image_bytes = request.get_data()

        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if is_blur(img):
            return jsonify({"status": "BLUR"})

        # 🔥 AUTO CENTER CROP
        h, w, _ = img.shape
        crop = img[h//4:3*h//4, w//4:3*w//4]

        _, buffer = cv2.imencode('.jpg', crop)
        text = extract_text(buffer.tobytes())

        if not is_invoice(text):
            return jsonify({"status": "NOT_INVOICE"})

        gst = find_gst(text)

        if not gst:
            return jsonify({"status": "GST_MISSING"})

        # FIREBASE DUPLICATE CHECK
        ref = db.reference("GST_HISTORY")
        data = ref.get() or {}

        if gst in data:
            return jsonify({"status": "DUPLICATE"})

        ref.child(gst).set(True)

        db.reference("LOGS").push({
            "gst": gst,
            "text": text
        })

        return jsonify({
            "status": "VALID_INVOICE",
            "gst": gst
        })

    except Exception as e:
        print("ERROR:", e)
        return jsonify({"status": "ERROR"})
