from flask import Flask, request, jsonify
from google.cloud import vision
import firebase_admin
from firebase_admin import credentials, db
import re
import time

app = Flask(__name__)

# ===== GOOGLE VISION CLIENT (SAFE INIT) =====
client = None

def get_client():
    global client
    if client is None:
        client = vision.ImageAnnotatorClient()
    return client

# ===== FIREBASE INIT =====
cred = credentials.Certificate("firebase-key.json")  # 🔥 file naam same hona chahiye
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://smart-gst-compliance-ae82d-default-rtdb.firebaseio.com/'
})

@app.route('/')
def home():
    return "🚀 OCR Server Running"

# ===== OCR FUNCTION =====
def extract_text(image_bytes):
    client = get_client()  # 🔥 important fix

    image = vision.Image(content=image_bytes)
    response = client.text_detection(image=image)

    texts = response.text_annotations

    if texts:
        return texts[0].description
    return ""

# ===== GST DETECT =====
def find_gst(text):
    pattern = r"\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d]"
    match = re.search(pattern, text)
    return match.group() if match else None

# ===== UPLOAD =====
@app.route('/upload', methods=['POST'])
def upload():

    image = request.data

    if not image:
        return {"error": "No image"}, 400

    print("📸 Image received")

    text = extract_text(image)
    print("🧠 OCR TEXT:", text)

    gst = find_gst(text)

    if not gst:
        alert = "❌ GST Missing"
    else:
        alert = f"✅ GST Found: {gst}"

    # ===== FIREBASE STORE (FINAL STRUCTURE 🔥) =====
    ref_latest = db.reference('GST_System/latest')
    ref_history = db.reference('GST_System/history')

    data = {
        "gst": gst if gst else "None",
        "alert": alert,
        "text": text,
        "timestamp": int(time.time())
    }

    # latest update
    ref_latest.set(data)

    # history save
    ref_history.push(data)

    return jsonify({
        "gst": gst,
        "alert": alert
    })

# ===== RUN =====
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
