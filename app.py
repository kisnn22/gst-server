from flask import Flask, request, jsonify
from google.cloud import vision
from google.oauth2 import service_account
import firebase_admin
from firebase_admin import credentials, db
import re
import time

app = Flask(__name__)

# ================= GOOGLE VISION =================
def init_vision():
    try:
        creds = service_account.Credentials.from_service_account_file("key.json")
        client = vision.ImageAnnotatorClient(credentials=creds)
        print("🔥 Vision Ready")
        return client
    except Exception as e:
        print("❌ Vision Error:", e)
        return None

vision_client = init_vision()

# ================= FIREBASE =================
try:
    cred = credentials.Certificate("key.json")
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://smart-gst-compliance-ae82d-default-rtdb.firebaseio.com/'
    })
    print("🔥 Firebase Connected")
except Exception as e:
    print("❌ Firebase Error:", e)

# ================= HOME =================
@app.route('/')
def home():
    return "🚀 GST OCR Server Running"

# ================= OCR =================
def extract_text(image_bytes):
    try:
        if not vision_client:
            return ""

        image = vision.Image(content=image_bytes)
        response = vision_client.text_detection(image=image)

        texts = response.text_annotations
        if texts:
            return texts[0].description

        return ""
    except Exception as e:
        print("❌ OCR Error:", e)
        return ""

# ================= GST FIND =================
def find_gst(text):
    pattern = r"\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d]"
    match = re.search(pattern, text)
    return match.group() if match else None

# ================= UPLOAD =================
@app.route('/upload', methods=['POST'])
def upload():

    try:
        image = request.get_data()

        if not image or len(image) < 100:
            return {"error": "Invalid image"}, 400

        print("🔥 STEP 1: Upload API HIT")

        # OCR
        text = extract_text(image)
        print("🔥 STEP 2: OCR DONE")

        # GST detect
        gst = find_gst(text)
        print("🔥 STEP 3: GST CHECK DONE")

        if not gst:
            alert = "❌ GST Missing"
            gst_value = "Not Found"
        else:
            alert = f"✅ GST Found: {gst}"
            gst_value = gst

        # FIREBASE SAVE
        try:
            print("🔥 STEP 4: Writing to Firebase...")

            ref = db.reference("GST_System")
            ref.set({
                "alert": alert,
                "gst_number": gst_value,
                "text": text,
                "timestamp": int(time.time())
            })

            print("🔥 STEP 5: Firebase SUCCESS")

        except Exception as e:
            print("❌ Firebase Write Error:", e)

        return jsonify({
            "alert": alert,
            "gst": gst_value
        })

    except Exception as e:
        print("🔥 SERVER ERROR:", e)
        return {"error": str(e)}, 500


# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
