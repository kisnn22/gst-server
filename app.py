from flask import Flask, request, jsonify
import re
import cv2
import numpy as np
from google.cloud import vision
import firebase_admin
from firebase_admin import credentials, db

app = Flask(__name__)

# FIREBASE
cred = credentials.Certificate("key.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'YOUR_FIREBASE_URL'
})

# VISION
client = vision.ImageAnnotatorClient()

# GST REGEX
def find_gst(text):
    pattern = r"\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d][Z][A-Z\d]"
    match = re.search(pattern, text)
    return match.group() if match else None

# BLUR CHECK
def is_blur(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    val = cv2.Laplacian(gray, cv2.CV_64F).var()
    return val < 100

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

        text = extract_text(image_bytes)

        # invoice check
        if "invoice" not in text.lower():
            return jsonify({"status": "NOT_INVOICE"})

        gst = find_gst(text)

        if not gst:
            return jsonify({"status": "GST_MISSING"})

        # duplicate check
        ref = db.reference("GST_HISTORY")
        data = ref.get() or {}

        if gst in data:
            return jsonify({"status": "DUPLICATE"})

        # save new GST
        ref.child(gst).set(True)

        # save full log
        db.reference("LOGS").push({
            "gst": gst,
            "text": text
        })

        return jsonify({
            "status": "VALID_INVOICE",
            "gst": gst
        })

    except Exception as e:
        print(e)
        return jsonify({"status": "ERROR"})
