from flask import Flask, request, jsonify
from google.cloud import vision
import firebase_admin
from firebase_admin import credentials, db
import re
import cv2
import numpy as np

app = Flask(__name__)

# FIREBASE (⚠️ CHANGE URL)
cred = credentials.Certificate("key.json")
firebase_admin.initialize_app(cred, {
    "databaseURL": "https://your-project-id-default-rtdb.firebaseio.com/"
})

client = vision.ImageAnnotatorClient()

# OCR
def extract_text(img):
    image = vision.Image(content=img)
    res = client.text_detection(image=image)
    texts = res.text_annotations
    return texts[0].description if texts else ""

# BLUR
def is_blur(img):
    arr = np.frombuffer(img, np.uint8)
    im = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if im is None:
        return True
    return cv2.Laplacian(im, cv2.CV_64F).var() < 40

# GST
def find_gst(text):
    m = re.findall(r"\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]", text)
    return m[0] if m else None

# INVOICE AI
def is_invoice(text):
    text = text.lower()

    keywords = ["invoice","bill","gst","tax","total","amount"]
    score = sum([1 for k in keywords if k in text])

    if find_gst(text):
        score += 5

    if len(text) > 80:
        score += 2

    print("SCORE:",score)
    return score >= 4

@app.route('/')
def home():
    return "🔥 SERVER LIVE"

@app.route('/upload', methods=['POST'])
def upload():

    img = request.get_data()

    if not img:
        return jsonify({"status":"ERROR"})

    if is_blur(img):
        return jsonify({"status":"BLUR"})

    text = extract_text(img)

    print("\nOCR TEXT:\n",text)

    if not is_invoice(text):
        return jsonify({"status":"NOT_INVOICE"})

    gst = find_gst(text)

    if not gst:
        return jsonify({"status":"GST_MISSING"})

    ref = db.reference("GST_HISTORY")
    data = ref.get() or {}

    if gst in data:
        return jsonify({"status":"DUPLICATE_GST"})

    ref.child(gst).set({"valid":True})

    return jsonify({
        "status":"VALID_INVOICE",
        "gst":gst
    })

if __name__ == "__main__":
    app.run()
