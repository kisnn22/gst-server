from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# ===== HOME ROUTE =====
@app.route('/')
def home():
    return "🚀 GST Server Running Successfully"

# ===== OCR FUNCTION =====
def extract_text(image_bytes):
    url = "https://api.ocr.space/parse/image"

    payload = {
        'apikey': 'helloworld',   # free key
        'language': 'eng'
    }

    files = {
        'file': ('invoice.jpg', image_bytes, 'image/jpeg')
    }

    try:
        r = requests.post(url, files=files, data=payload, timeout=10)
        result = r.json()

        if "ParsedResults" in result:
            return result['ParsedResults'][0]['ParsedText']
        else:
            return ""

    except Exception as e:
        print("❌ OCR ERROR:", e)
        return ""

# ===== UPLOAD ROUTE =====
@app.route('/upload', methods=['POST'])
def upload():

    try:
        image = request.data

        if not image:
            return jsonify({"error": "No image received"}), 400

        print("\n📸 Image received:", len(image), "bytes")

        # ===== OCR PROCESS =====
        text = extract_text(image)
        print("🧠 OCR TEXT:\n", text)

        # ===== GST LOGIC =====
        if "GST" not in text:
            alert = "❌ GST Missing"
        elif "Duplicate" in text:
            alert = "⚠️ Duplicate Invoice"
        else:
            alert = "✅ Valid Invoice"

        print("🔍 FINAL ALERT:", alert)

        # ===== RESPONSE =====
        return jsonify({
            "status": "success",
            "text": text,
            "alert": alert
        }), 200

    except Exception as e:
        print("❌ SERVER ERROR:", e)
        return jsonify({"error": "Server Failed"}), 500

# ===== RUN SERVER =====
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
