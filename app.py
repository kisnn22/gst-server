from flask import Flask, request

app = Flask(__name__)

# ✅ ROOT ROUTE
@app.route('/')
def home():
    return "Server Running 🚀"

# ✅ UPLOAD ROUTE
@app.route('/upload', methods=['POST'])
def upload():
    try:
        image = request.data

        if not image:
            return {"error": "No image received"}, 400

        print("✅ Image received")

        return {"text": "GST FOUND"}, 200

    except Exception as e:
        return {"error": str(e)}, 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
