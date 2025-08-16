# SteganoVault — Image Steganography (LSB)

Flask-based web app to encode and decode hidden data inside images using Least Significant Bit (LSB).

- Encode: Hide text or a small file inside a cover image.
- Decode: Extract the hidden file (original filename preserved if provided).

PNG is recommended to preserve exact pixel bits.

## Setup

1. Create and activate a virtual environment (Windows PowerShell):
   ```powershell
   python -m venv .venv
   .venv\\Scripts\\Activate.ps1
   ```
2. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
3. Run the app:
   ```powershell
   python app.py
   ```
4. Open http://127.0.0.1:5000 in your browser.

## Usage

- Top glass buttons toggle between Encode and Decode panels.
- Drag & drop an image into the dropzone or click to browse.
- Encode:
  - Choose Mode = Text or File.
  - Enter text or select a payload file.
  - Click "Encode & Download" to get stego.png.
- Decode:
  - Provide a stego image.
  - Click "Decode & Download" to retrieve the payload.

## How it works

- 1 LSB per channel (R,G,B) is used. Capacity = width * height * 3 bits.
- A small header is embedded containing a magic string, payload length, and filename, followed by the payload.
 

## Notes

- Prefer high-resolution PNG covers for larger capacity.
- JPEG recompression can break stego bits; the app always outputs PNG.
- Very large payloads may exceed capacity; the app will report how many bits are needed vs available.

## Requirements

- Python 3.10+
- pip
- OS: Windows/macOS/Linux

## Quick Start

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1  # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py
# open http://127.0.0.1:5000
```

## cURL examples

Encode text into an image:

```bash
curl -X POST http://127.0.0.1:5000/encode \
  -F "mode=text" \
  -F "image=@cover.png" \
  -F "text=Hidden message" \
  -o stego.png
```

Encode a file:

```bash
curl -X POST http://127.0.0.1:5000/encode \
  -F "mode=file" \
  -F "image=@cover.png" \
  -F "payload=@secret.pdf" \
  -o stego.png
```

Decode from a stego image:

```bash
curl -X POST http://127.0.0.1:5000/decode \
  -F "image=@stego.png" \
  -OJ
```

## Limitations & Security

- LSB is not encryption. For sensitive data, encrypt before embedding.
- Lossy formats (JPEG) may destroy hidden bits; always keep PNG for output.
- Capacity is finite; large payloads won’t fit. Use the smallest payloads possible.

## Troubleshooting

- "Payload exceeds capacity": try a larger cover image or a smaller payload.
- "Invalid image" or decode errors: ensure the image is the exact stego PNG created by the app.
- If Flask won’t start, check that the virtual environment is active and dependencies are installed.

## Project structure

```
steg-app/
├─ app.py           # Flask server routes
├─ stego.py         # LSB encode/decode logic
├─ templates/
│  └─ index.html    # UI (tabs + drag-and-drop)
├─ static/
│  ├─ favicon.svg   # App icon
│  └─ style.css     # (optional legacy stylesheet)
├─ requirements.txt
└─ README.md
```

## License

MIT (see LICENSE if provided). Otherwise, treat as permissive for personal/educational use.
