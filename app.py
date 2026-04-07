from flask import Flask, request, jsonify
from google.cloud import vision
import firebase_admin
from firebase_admin import credentials, db
import re
import cv2
import numpy as np

app = Flask(__name__)

# Firebase
cred = credentials.Certificate("key.json")
firebase_admin.initialize_app(cred, {
    "databaseURL": "https://your-db.firebaseio.com/"
})

client = vision.ImageAnnotatorClient()

# OCR
def extract_text(image_bytes):
    image = vision.Image(content=image_bytes)
    response = client.text_detection(image=image)
    texts = response.text_annotations
    return texts[0].description if texts else ""

# GST
def find_gst(text):
    match = re.findall(r"\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d]", text)
    return match[0] if match else None

# BLUR
def is_blur(image_bytes):
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
    return cv2.Laplacian(img, cv2.CV_64F).var() < 50

# 🔥 AUTO-ZOOM AND MAP PERSPECTIVE 
# 🔥 BULLETPROOF AUTO-ZOOM 
def crop_invoice(image_bytes):
    try:
        # Decode image safely
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            return False, image_bytes

        # Grayscale, blur, and edge detection
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(gray, 75, 200)

        # Find the contours safely across all versions of OpenCV
        cnts = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        contours = cnts[0] if len(cnts) == 2 else cnts[1]
        
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
        
        screen_cnt = None
        for cnt in contours:
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
            if len(approx) == 4 and cv2.contourArea(cnt) > 5000:
                screen_cnt = approx
                break
                
        if screen_cnt is None:
            return False, image_bytes
            
        pts = screen_cnt.reshape(4, 2)
        rect = np.zeros((4, 2), dtype="float32")
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]

        (tl, tr, br, bl) = rect

        widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        maxWidth = max(int(widthA), int(widthB))

        heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        maxHeight = max(int(heightA), int(heightB))

        dst = np.array([
            [0, 0],
            [maxWidth - 1, 0],
            [maxWidth - 1, maxHeight - 1],
            [0, maxHeight - 1]], dtype="float32")

        M = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(img, M, (maxWidth, maxHeight))

        warped_gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
        
        is_success, buffer = cv2.imencode(".jpg", warped_gray)
        if is_success:
            return True, buffer.tobytes()
            
    except Exception as e:
        # If absolutely anything fails, it catches it and safely ignores zooming!
        print("Safely ignoring crop error:", e)
        
    return False, image_bytes

# 🔥 FINAL LOGIC
def is_invoice(text):
    # STEP: text check
    if len(text) < 50:
        return False

    score = 0

    if "invoice" in text.lower(): score += 3
    if "gst" in text.lower(): score += 3
    if "total" in text.lower(): score += 1

    if find_gst(text):
        score += 5

    return score >= 6

@app.route('/')
def home():
    return "GST AI SERVER RUNNING"

import traceback

@app.route('/upload', methods=['POST'])
def upload():
    try:
        image = request.get_data()

        if not image:
            return jsonify({"status": "ERROR"})

        # --- STEP 1: Process and flatten the image first! ---
        has_shape, processed_image = crop_invoice(image)

        # --- STEP 2: Feed the perfectly flat, cropped image to Google Cloud Vision ---
        text = extract_text(processed_image)

        # --- STEP 3: Validate the text ---
        if not is_invoice(text):
            return jsonify({"status": "NOT_INVOICE"})

        gst = find_gst(text)

        if not gst:
            return jsonify({"status": "GST_MISSING"})

        ref = db.reference("GST_HISTORY")
        data = ref.get() or {}

        if gst in data:
            return jsonify({"status": "DUPLICATE_GST"})

        ref.child(gst).set({"ok": True})

        return jsonify({"status": "VALID_INVOICE", "gst": gst})
        
    except Exception as e:
        # If the server crashes, it catches the exact error and sends it to the Arduino!
        print("CRASH LOG:", traceback.format_exc())
        return jsonify({"status": "PYTHON_CRASH", "error": str(e)})

if __name__ == "__main__":
    app.run()
