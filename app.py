from flask import Flask, request, jsonify
from google.cloud import vision
import firebase_admin
from firebase_admin import credentials, db
import re

app = Flask(__name__)

# ===== FIREBASE INIT =====
cred = credentials.Certificate("key.json")  # 🔥 tera firebase key file
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://smart-gst-compliance-ae82d-default-rtdb.firebaseio.com/'
})

# ===== GOOGLE VISION =====
client = vision.ImageAnnotatorClient()

@app.route('/')
def home():
    return "🚀 Server Running with Firebase"

# ===== OCR =====
def extract_text(image_bytes):
    image = vision.Image(content=image_bytes)
    response = client.text_detection(image=image)

    texts = response.text_annotations

    if texts:
        return texts[0].description
    return ""

# ===== GST FIND =====
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
    gst = find_gst(text)

    if not gst:
        alert = "❌ GST Missing"
        gst_value = "Not Found"
    else:
        alert = "✅ GST Found"
        gst_value = gst

    print("📊 RESULT:", alert, gst_value)

    # 🔥🔥🔥 FIREBASE PUSH
    db.reference("GST_System").set({
        "alert": alert,
        "gst_number": gst_value,
        "raw_text": text
    })

    return jsonify({
        "alert": alert,
        "gst": gst_value
    })
