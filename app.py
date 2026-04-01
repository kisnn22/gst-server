from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, db
from google.cloud import vision
import re
import os

app = Flask(__name__)

# ===== FIREBASE =====
cred = credentials.Certificate("key.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://smart-gst-compliance-ae82d-default-rtdb.firebaseio.com/'
})

print("🔥 Firebase Connected")

# ===== GOOGLE VISION =====
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "key.json"
client = vision.ImageAnnotatorClient()

print("🔥 Vision Ready")

# ===== OCR FUNCTION =====
def extract_text(image_bytes):
    image = vision.Image(content=image_bytes)
    response = client.text_detection(image=image)

    texts = response.text_annotations
    if texts:
        return texts[0].description
    return ""

# ===== GST DETECTION =====
def find_gst(text):
    pattern = r"\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}Z[A-Z\d]{1}\b"
    match = re.search(pattern, text)
    return match.group() if match else None

# ===== INVOICE CHECK =====
def is_invoice(text):
    keywords = ["invoice", "bill", "gst", "tax"]
    text = text.lower()
    return any(word in text for word in keywords)

# ===== BLUR CHECK =====
def is_blur(text):
    return len(text) < 20

# ===== ROUTES =====
@app.route('/')
def home():
    return "GST SERVER RUNNING"

@app.route('/upload', methods=['POST'])
def upload():
    try:
        image = request.get_data()

        if not image:
            return jsonify({"error": "No image"}), 400

        print("🔥 STEP 1: Upload API HIT")

        text = extract_text(image)
        print("🧾 OCR TEXT:\n", text)

        # ===== BLUR CHECK =====
        if is_blur(text):
            return jsonify({"alert": "blur"})

        # ===== INVOICE CHECK =====
        if not is_invoice(text):
            return jsonify({"alert": "not_invoice"})

        gst = find_gst(text)

        if not gst:
            alert = "❌ GST Missing"
            gst_value = "Not Found"
        else:
            alert = "✅ GST Found"
            gst_value = gst

        print("🔥 STEP 3: GST:", gst_value)

        # ===== SAVE TO FIREBASE =====
        ref = db.reference("GST_System/history")
        ref.push({
            "alert": alert,
            "gst_number": gst_value,
            "text": text
        })

        print("🔥 Firebase Saved")

        return jsonify({
            "alert": alert,
            "gst": gst_value
        })

    except Exception as e:
        print("🔥 SERVER ERROR:", e)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run()
