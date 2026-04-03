from flask import Flask, request, jsonify
from google.cloud import vision
import firebase_admin
from firebase_admin import credentials, db
import re
import cv2
import numpy as np
from tensorflow.keras.applications.mobilenet_v2 import MobileNetV2, preprocess_input
from tensorflow.keras.preprocessing.image import img_to_array

app = Flask(__name__)

# Firebase
cred = credentials.Certificate("key.json")
firebase_admin.initialize_app(cred, {
    "databaseURL": "https://your-db.firebaseio.com/"
})

client = vision.ImageAnnotatorClient()

# AI MODEL
model = MobileNetV2(weights="imagenet")

# OCR
def extract_text(image_bytes):
    image = vision.Image(content=image_bytes)
    response = client.text_detection(image=image)
    texts = response.text_annotations
    return texts[0].description if texts else ""

# GST FIND
def find_gst(text):
    match = re.findall(r"\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d]", text)
    return match[0] if match else None

# BLUR
def is_blur(image_bytes):
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
    return cv2.Laplacian(img, cv2.CV_64F).var() < 50

# 🔥 CONTOUR DETECTION (INVOICE SHAPE)
def detect_paper(image_bytes):
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for cnt in contours:
        approx = cv2.approxPolyDP(cnt, 0.02 * cv2.arcLength(cnt, True), True)
        if len(approx) == 4:
            area = cv2.contourArea(cnt)
            if area > 5000:
                return True
    return False

# 🔥 AI IMAGE CHECK
def is_invoice_ai(image_bytes):
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    img = cv2.resize(img, (224, 224))

    img = img_to_array(img)
    img = preprocess_input(img)
    img = np.expand_dims(img, axis=0)

    preds = model.predict(img)

    # MobileNet generic check (paper-like objects)
    confidence = np.max(preds)

    return confidence > 0.5

# 🔥 FINAL INVOICE CHECK (COMBINED)
def is_invoice(text, image_bytes):

    # STEP 1: AI Image check
    if not is_invoice_ai(image_bytes):
        return False

    # STEP 2: Paper detection
    if not detect_paper(image_bytes):
        return False

    # STEP 3: OCR validation
    if len(text) < 50:
        return False

    score = 0
    if "invoice" in text.lower(): score += 3
    if "gst" in text.lower(): score += 3
    if "total" in text.lower(): score += 1

    if find_gst(text):
        score += 5

    return score >= 6

# API
@app.route('/')
def home():
    return "AI GST SERVER RUNNING"

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

    # Duplicate check
    ref = db.reference("GST_HISTORY")
    data = ref.get() or {}

    if gst in data:
        return jsonify({"status": "DUPLICATE_GST"})

    ref.child(gst).set({"ok": True})

    return jsonify({"status": "VALID_INVOICE", "gst": gst})

if __name__ == "__main__":
    app.run()
