from flask import Flask, request, jsonify
import cv2
import numpy as np
import re
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)

# ===== FIREBASE =====
cred = credentials.Certificate("key.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# ===== GST REGEX =====
gst_pattern = r'\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}'

# ===== BLUR CHECK =====
def is_blur(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var() < 100

# ===== INVOICE CHECK =====
def is_invoice(text):
    keywords = ["invoice", "gst", "bill", "tax"]
    return any(k in text.lower() for k in keywords)

# ===== OCR =====
def get_text(img):
    import pytesseract
    return pytesseract.image_to_string(img)

# ===== ROUTE =====
@app.route('/upload', methods=['POST'])
def upload():

    file_bytes = np.frombuffer(request.data, np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

    if img is None:
        return jsonify({"error": "no image"})

    # BLUR CHECK
    if is_blur(img):
        return jsonify({"status": "blur"})

    text = get_text(img)

    # INVOICE DETECTION
    if not is_invoice(text):
        return jsonify({"status": "not_invoice"})

    # GST FIND
    gst_numbers = re.findall(gst_pattern, text)

    if not gst_numbers:
        return jsonify({"status": "no_gst"})

    gst = gst_numbers[0]

    # DUPLICATE CHECK
    existing = db.collection("gst").document(gst).get()

    if existing.exists:
        return jsonify({"status": "duplicate"})

    # SAVE
    db.collection("gst").document(gst).set({
        "gst": gst
    })

    return jsonify({
        "status": "valid",
        "gst": gst
    })


# ===== RUN =====
if __name__ == "__main__":
    app.run()
