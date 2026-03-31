from flask import Flask, request, jsonify
from google.cloud import vision

app = Flask(__name__)

# Google Vision client
client = vision.ImageAnnotatorClient()

@app.route('/')
def home():
    return "🚀 OCR Server Running"

# OCR FUNCTION
def extract_text(image_bytes):
    image = vision.Image(content=image_bytes)
    response = client.text_detection(image=image)

    texts = response.text_annotations

    if texts:
        return texts[0].description
    return ""

# GST DETECT FUNCTION (ADVANCED 🔥)
import re
def find_gst(text):
    pattern = r"\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d]"
    match = re.search(pattern, text)
    return match.group() if match else None

# UPLOAD
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

    return jsonify({
        "text": text,
        "alert": alert
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
