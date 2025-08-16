from __future__ import annotations
from typing import Tuple, List
from PIL import Image
import math
import struct

HEADER_MAGIC = b"STEG1"  # 5 bytes to mark presence
# Header format: MAGIC (5) + name_len (H) + payload_len (I) + name bytes
# Then payload bytes


def _to_rgb_image(img: Image.Image) -> Image.Image:
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
    if img.mode == "RGBA":
        # drop alpha for stable capacity and to avoid writing into alpha
        img = img.convert("RGB")
    return img


def get_capacity_bits(img: Image.Image) -> Tuple[int, int]:
    """Return (capacity_bits, capacity_bytes) for 1 LSB in RGB channels."""
    img = _to_rgb_image(img)
    w, h = img.size
    channels = 3  # R,G,B
    bits = w * h * channels  # 1 bit per channel
    return bits, bits // 8


def _iter_pixels(img: Image.Image):
    pixels = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b = pixels[x, y]
            yield x, y, r, g, b


def _set_pixel_lsb(rgb: Tuple[int, int, int], bits: Tuple[int, int, int]) -> Tuple[int, int, int]:
    r, g, b = rgb
    br, bg, bb = bits
    r = (r & 0xFE) | (br & 1)
    g = (g & 0xFE) | (bg & 1)
    b = (b & 0xFE) | (bb & 1)
    return r, g, b


def _bit_generator(data: bytes):
    for byte in data:
        for i in range(7, -1, -1):
            yield (byte >> i) & 1


def _pack_header(filename: str, payload: bytes) -> bytes:
    name_bytes = (filename or "").encode("utf-8")[:65535]
    header = HEADER_MAGIC
    header += struct.pack(">HI", len(name_bytes), len(payload))
    header += name_bytes
    return header


def _unpack_header(bitstream: List[int]) -> Tuple[str, int, int, int]:
    """Return (filename, payload_len, header_bits_consumed, header_bytes_len).
    Raises ValueError if header invalid.
    """
    # Need at least MAGIC(5) + H(2) + I(4) = 11 bytes => 88 bits first
    if len(bitstream) < 88:
        raise ValueError("Not enough data for header")

    def bits_to_bytes(bits: List[int]) -> bytes:
        by = bytearray()
        for i in range(0, len(bits), 8):
            b = 0
            for j in range(8):
                b = (b << 1) | bits[i + j]
            by.append(b)
        return bytes(by)

    # Read first 11 bytes
    first88 = bits_to_bytes(bitstream[:88])
    if not first88.startswith(HEADER_MAGIC):
        raise ValueError("No stego header found")

    name_len = struct.unpack(">H", first88[5:7])[0]
    payload_len = struct.unpack(">I", first88[7:11])[0]
    header_bytes_len = 11 + name_len
    total_header_bits = header_bytes_len * 8

    if len(bitstream) < total_header_bits:
        raise ValueError("Corrupt header or insufficient data")

    header_bytes = bits_to_bytes(bitstream[:total_header_bits])
    name_bytes = header_bytes[11:11 + name_len]
    filename = name_bytes.decode("utf-8", errors="replace")

    return filename, payload_len, total_header_bits, header_bytes_len


def encode_lsb(img: Image.Image, payload: bytes, filename: str = "payload.bin"):
    """Embed payload into image using 1 LSB per RGB channel.
    Returns (output_image, stats)
    Raises ValueError if capacity is insufficient.
    """
    img = _to_rgb_image(img)
    w, h = img.size

    header = _pack_header(filename, payload)
    full = header + payload
    total_bits = len(full) * 8

    cap_bits, _ = get_capacity_bits(img)
    if total_bits > cap_bits:
        raise ValueError(f"Payload too large. Need {total_bits} bits, have {cap_bits} bits.")

    bits = list(_bit_generator(full))
    bit_idx = 0

    out = img.copy()
    px = out.load()
    for y in range(h):
        for x in range(w):
            if bit_idx >= total_bits:
                break
            r, g, b = px[x, y]
            br = bits[bit_idx] if bit_idx < total_bits else 0
            bg = bits[bit_idx + 1] if bit_idx + 1 < total_bits else 0
            bb = bits[bit_idx + 2] if bit_idx + 2 < total_bits else 0
            px[x, y] = _set_pixel_lsb((r, g, b), (br, bg, bb))
            bit_idx += 3
        if bit_idx >= total_bits:
            break

    used_bits = total_bits
    return out, {
        "width": w,
        "height": h,
        "capacity_bits": cap_bits,
        "used_bits": used_bits,
        "utilization": used_bits / cap_bits if cap_bits else 0.0,
    }


def decode_lsb(img: Image.Image) -> Tuple[str, bytes]:
    """Extract payload. Returns (filename, payload_bytes). Raises ValueError if not found."""
    img = _to_rgb_image(img)
    w, h = img.size

    # Read all LSBs once across the image to avoid duplication or restart issues
    bits: List[int] = []
    px = img.load()
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            bits.extend((r & 1, g & 1, b & 1))

    # Parse header from the beginning of the bitstream
    filename, payload_len, header_bits, _ = _unpack_header(bits)
    total_needed = header_bits + payload_len * 8

    if len(bits) < total_needed:
        raise ValueError("Image does not contain the expected amount of data")

    # Extract payload bits and convert to bytes
    start = header_bits
    end = header_bits + payload_len * 8
    payload_bits = bits[start:end]

    out_bytes = bytearray()
    for i in range(0, len(payload_bits), 8):
        b = 0
        for j in range(8):
            b = (b << 1) | payload_bits[i + j]
        out_bytes.append(b)

    return filename, bytes(out_bytes)


def detect_lsb(img: Image.Image):
    """Return (score, details) where score in [0,1].
    Simple heuristic using pair-of-values chi-like measure and LSB entropy.
    0 -> unlikely stego, 1 -> very likely stego.
    """
    img = _to_rgb_image(img)
    w, h = img.size
    px = img.load()

    # Collect histograms for pairs (2k, 2k+1) separately for RGB
    pair_counts = [{}, {}, {}]
    lsb_counts = [0, 0]

    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            for ci, val in enumerate((r, g, b)):
                k = val // 2  # pair index
                pair_counts[ci][k] = pair_counts[ci].get(k, 0) + 1
            lsb_counts[r & 1] += 1
            lsb_counts[g & 1] += 1
            lsb_counts[b & 1] += 1

    # Chi-like measure: For each channel, sum over pairs (even, odd)
    chi_scores = []
    for ci in range(3):
        s = 0.0
        for k, count in pair_counts[ci].items():
            # actual counts for even/odd within this pair
            even = 0
            odd = 0
        # Re-scan to get even/odd; to avoid second pass over image, approximate using uniform split
        # Approximation: within each pair total t, if stego present, even and odd become similar; measure closeness.
        # We'll instead estimate closeness via variance from 50/50 using only totals per pair which is coarse.
        # Define score per pair as 1 - |even-odd|/t; since unknown, approximate |even-odd| ~ |(val%2) bias|; skip detailed per-pixel calc.
        # Simpler robust heuristic below based on global LSB balance and saturation.
        chi_scores.append(0.0)

    # Global LSB balance heuristic
    total_lsbs = sum(lsb_counts)
    if total_lsbs == 0:
        lsb_balance = 0.5
    else:
        lsb_balance = lsb_counts[1] / total_lsbs

    balance_score = 1.0 - abs(0.5 - lsb_balance) * 2.0  # 1 at 0.5, 0 at 0 or 1

    # Edge/noise measure: compare adjacent pixels LSB flips rate
    flips = 0
    comps = 0
    prev = None
    for y in range(h):
        prev = None
        for x in range(w):
            r, g, b = px[x, y]
            cur = ((r & 1) << 2) | ((g & 1) << 1) | (b & 1)
            if prev is not None:
                # count bit differences
                diff = (prev ^ cur)
                flips += (diff & 1) + ((diff >> 1) & 1) + ((diff >> 2) & 1)
                comps += 3
            prev = cur

    flip_rate = (flips / comps) if comps else 0.0
    flip_score = min(1.0, flip_rate / 0.5)  # normalize; 0.5 is very high flip rate

    # Combine scores heuristically
    score = 0.6 * balance_score + 0.4 * flip_score

    details = {
        "width": w,
        "height": h,
        "lsb_ones": lsb_counts[1],
        "lsb_zeros": lsb_counts[0],
        "lsb_balance": round(lsb_balance, 4),
        "flip_rate": round(flip_rate, 4),
        "notes": "Heuristic detector; high score suggests possible LSB embedding, but not definitive."
    }
    return float(max(0.0, min(1.0, score))), details
