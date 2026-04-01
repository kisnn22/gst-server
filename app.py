from flask import Flask, request, jsonify
from google.cloud import vision
import firebase_admin
from firebase_admin import credentials, db
import re, os, cv2, numpy as np
from datetime import datetime

app = Flask(__name__)

# ===== GOOGLE VISION =====
client = vision.ImageAnnotatorClient()

# ===== FIREBASE =====
cred = credentials.Certificate("key.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://smart-gst-compliance-ae82d-default-rtdb.firebaseio.com/'
})

print("🔥 Firebase Connected")

# ===== OCR =====
def extract_text(image_bytes):
    image = vision.Image(content=image_bytes)
    response = client.text_detection(image=image)
    texts = response.text_annotations
    return texts[0].description if texts else ""

# ===== GST FIND =====
def find_gst(text):
    pattern = r"\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d]"
    match = re.search(pattern, text)
    return match.group() if match else None

# ===== BLUR CHECK =====
def is_blurry(image_bytes):
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
    val = cv2.Laplacian(img, cv2.CV_64F).var()
    print("Blur:", val)
    return val < 100

# ===== DUPLICATE CHECK =====
def is_duplicate(gst):
    ref = db.reference("history")
    data = ref.get()

    if data:
        for key in data:
            if data[key]["gst"] == gst:
                return True
    return False

# ===== ROUTE =====
@app.route('/')
def home():
    return "Server Running 🚀"

@app.route('/upload', methods=['POST'])
def upload():

    image = request.data

    if not image:
        return {"error": "No image"}, 400

    print("🔥 Upload Received")

    # Blur check
    if is_blurry(image):
        return jsonify({"alert": "blur"})

    text = extract_text(image)
    print("OCR:", text)

    gst = find_gst(text)

    if not gst:
        alert = "❌ GST Missing"
        status = "invalid"

    else:
        if is_duplicate(gst):
            alert = "🚨 Duplicate Invoice"
            status = "fraud"
        else:
            alert = f"✅ GST Found: {gst}"
            status = "valid"

    # SAVE HISTORY
    db.reference("history").push({
        "gst": gst,
        "text": text,
        "status": status,
        "time": str(datetime.now())
    })

    # LIVE NODE
    db.reference("GST_System").set({
        "alert": alert,
        "gst": gst,
        "status": status
    })

    return jsonify({
        "alert": alert,
        "status": status
    })

if __name__ == "__main__":
    app.run()
