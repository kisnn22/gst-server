from flask import Flask, request, jsonify
from google.cloud import vision
import firebase_admin
from firebase_admin import credentials, db
import numpy as np
import cv2
import re
import datetime

app = Flask(__name__)

# ===== GOOGLE VISION =====
client = vision.ImageAnnotatorClient()

# ===== FIREBASE =====
cred = credentials.Certificate("key.json")
firebase_admin.initialize_app(cred, {
    "databaseURL": "https://YOUR_DB.firebaseio.com/"
})

# ===== GST REGEX (STRONG) =====
gst_pattern = r"\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d]"

# ===== CLEAN TEXT =====
def clean_text(text):
    text = text.upper()
    text = text.replace(" ", "")
    text = text.replace("\n", "")
    return text

# ===== BLUR CHECK =====
def is_blur(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var() < 60

# ===== OCR =====
def extract_text(img_bytes):
    image = vision.Image(content=img_bytes)
    response = client.text_detection(image=image)
    texts = response.text_annotations
    return texts[0].description if texts else ""

# ===== INVOICE CHECK =====
def is_invoice(text):
    words = ["INVOICE", "BILL", "GST", "TAX"]
    return any(w in text.upper() for w in words)

# ===== ROUTE =====
@app.route('/')
def home():
    return "🚀 GST AI SERVER RUNNING"

@app.route('/upload', methods=['POST'])
def upload():

    print("\n🔥 NEW REQUEST")

    image_bytes = request.get_data()

    npimg = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(npimg, cv2.IMREAD_COLOR)

    # ===== BLUR =====
    if is_blur(img):
        return jsonify({"status": "BLUR"})

    # ===== OCR =====
    raw_text = extract_text(image_bytes)
    clean = clean_text(raw_text)

    print("🧠 RAW:", raw_text)
    print("🧹 CLEAN:", clean)

    # ===== INVOICE CHECK =====
    if not is_invoice(raw_text):
        return jsonify({"status": "NOT_INVOICE"})

    # ===== GST FIND =====
    gst_list = re.findall(gst_pattern, clean)

    if not gst_list:
        return jsonify({"status": "GST_MISSING"})

    gst = gst_list[0]

    # ===== DUPLICATE =====
    ref = db.reference("GST_History")
    data = ref.get()

    if data:
        for k in data:
            if data[k]["gst"] == gst:
                return jsonify({"status": "DUPLICATE", "gst": gst})

    # ===== SAVE =====
    ref.push({
        "gst": gst,
        "text": raw_text,
        "time": str(datetime.datetime.now())
    })

    return jsonify({
        "status": "VALID_INVOICE",
        "gst": gst
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
