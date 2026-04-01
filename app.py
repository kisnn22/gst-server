from flask import Flask, request, jsonify
import base64

app = Flask(__name__)

@app.route('/')
def home():
    return "Server Running 🚀"

@app.route('/upload', methods=['POST'])
def upload():
    try:
        print("🔥 API HIT")

        image = request.get_data()

        if not image:
            return jsonify({"status": "NO_IMAGE"})

        print("📸 Image Received")

        # 👉 TEMP TEST RESPONSE (IMPORTANT)
        return jsonify({
            "status": "VALID_INVOICE"
        })

    except Exception as e:
        print("❌ ERROR:", e)
        return jsonify({
            "status": "ERROR"
        })
