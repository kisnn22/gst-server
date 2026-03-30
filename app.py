from flask import Flask, request
import requests

app = Flask(__name__)

# ===== HOME =====
@app.route('/')
def home():
    return "Server Running 🚀"

# ===== OCR FUNCTION =====
def extract_text(image):
    url = "https://api.ocr.space/parse/image"
    payload = {
        'apikey': 'helloworld',
        'language': 'eng'
    }

    files = {
        'file': ('image.jpg', image)
    }

    r = requests.post(url, files=files, data=payload)
    result = r.json()

    try:
        return result['ParsedResults'][0]['ParsedText']
    except:
        return ""

# ===== UPLOAD =====
@app.route('/upload', methods=['POST'])
def upload():

    image = request.data

    if not image:
        return {"error": "No image"}, 400

    print("📸 Image received")

    # 🔥 OCR
    text = extract_text(image)
    print("🧠 OCR TEXT:", text)

    # 🔥 GST LOGIC
    if "GST" not in text:
        alert = "❌ GST Missing"
    elif "Duplicate" in text:
        alert = "⚠️ Duplicate Invoice"
    else:
        alert = "✅ Valid Invoice"

    return {
        "text": text,
        "alert": alert
    }, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
