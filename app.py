from flask import Flask, request, jsonify, render_template, send_file
from io import BytesIO
from PIL import Image
import os
from stego import encode_lsb, decode_lsb, detect_lsb, get_capacity_bits

app = Flask(__name__, template_folder="templates", static_folder="static")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/capacity", methods=["POST"])
def capacity():
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400
    f = request.files["image"]
    try:
        img = Image.open(f.stream)
        cap_bits, cap_bytes = get_capacity_bits(img)
        return jsonify({
            "capacity_bits": cap_bits,
            "capacity_bytes": cap_bytes
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/encode", methods=["POST"])
def encode():
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    mode = request.form.get("mode", "text")  # 'text' or 'file'
    text = request.form.get("text", "")
    file_payload = request.files.get("payload")

    if mode == "text":
        payload = text.encode("utf-8")
        payload_name = "message.txt"
    elif mode == "file":
        if file_payload is None or file_payload.filename == "":
            return jsonify({"error": "No payload file uploaded"}), 400
        payload = file_payload.read()
        payload_name = os.path.basename(file_payload.filename)
    else:
        return jsonify({"error": "Invalid mode"}), 400

    try:
        base_img = Image.open(request.files["image"].stream)
        out_img, stats = encode_lsb(base_img, payload, payload_name)

        bio = BytesIO()
        out_img.save(bio, format="PNG")  # always PNG to preserve bits
        bio.seek(0)
        return send_file(
            bio,
            mimetype="image/png",
            as_attachment=True,
            download_name="stego.png",
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Encoding failed: {e}"}), 500


@app.route("/decode", methods=["POST"])
def decode():
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400
    try:
        img = Image.open(request.files["image"].stream)
        filename, payload_bytes = decode_lsb(img)
        # Return as a downloadable file
        bio = BytesIO(payload_bytes)
        bio.seek(0)
        safe_name = filename if filename else "payload.bin"
        return send_file(bio, as_attachment=True, download_name=safe_name)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Decoding failed: {e}"}), 500


@app.route("/detect", methods=["POST"])
def detect():
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400
    try:
        img = Image.open(request.files["image"].stream)
        score, details = detect_lsb(img)
        return jsonify({
            "suspicion_score": score,  # 0.0 (unlikely) .. 1.0 (very likely)
            "details": details,
        })
    except Exception as e:
        return jsonify({"error": f"Detection failed: {e}"}), 500



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
