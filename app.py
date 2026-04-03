from flask import Flask, request, jsonify
from google.cloud import vision
import firebase_admin
from firebase_admin import credentials, db
import re
import cv2
import numpy as np

app = Flask(__name__)

# Firebase
cred = credentials.Certificate("key.json")
firebase_admin.initialize_app(cred, {
    "databaseURL": "https://your-db.firebaseio.com/"
})

client = vision.ImageAnnotatorClient()

# OCR
def extract_text(image_bytes):
    image = vision.Image(content=image_bytes)
    response = client.text_detection(image=image)
    texts = response.text_annotations
    return texts[0].description if texts else ""

# GST
def find_gst(text):
    match = re.findall(r"\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d]", text)
    return match[0] if match else None

# BLUR
def is_blur(image_bytes):
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
    return cv2.Laplacian(img, cv2.CV_64F).var() < 50

# 🔥 PAPER DETECTION (AI SUBSTITUTE)
def detect_invoice_shape(image_bytes):
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for cnt in contours:
        approx = cv2.approxPolyDP(cnt, 0.02 * cv2.arcLength(cnt, True), True)
        area = cv2.contourArea(cnt)

        if len(approx) == 4 and area > 5000:
            return True

    return False

# 🔥 FINAL LOGIC
def is_invoice(text, image_bytes):

    # STEP 1: shape detection
    if not detect_invoice_shape(image_bytes):
        return False

    # STEP 2: text check
    if len(text) < 50:
        return False

    score = 0

    if "invoice" in text.lower(): score += 3
    if "gst" in text.lower(): score += 3
    if "total" in text.lower(): score += 1

    if find_gst(text):
        score += 5

    return score >= 6

@app.route('/')
def home():
    return "GST AI SERVER RUNNING"

@app.route('/upload', methods=['POST'])
def upload():

    image = request.get_data()

    if not image:
        return jsonify({"status": "ERROR"})

    if is_blur(image):
        return jsonify({"status": "BLUR"})

    text = extract_text(image)

    if not is_invoice(text, image):
        return jsonify({"status": "NOT_INVOICE"})

    gst = find_gst(text)

    if not gst:
        return jsonify({"status": "GST_MISSING"})

    ref = db.reference("GST_HISTORY")
    data = ref.get() or {}

    if gst in data:
        return jsonify({"status": "DUPLICATE_GST"})

    ref.child(gst).set({"ok": True})

    return jsonify({"status": "VALID_INVOICE", "gst": gst})

if __name__ == "__main__":
    app.run()
