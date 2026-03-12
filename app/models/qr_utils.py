import qrcode
import os

def generate_product_qr(product_id: str):

    url = f"http://localhost:8000/products/{product_id}"

    qr = qrcode.make(url)

    folder = "static/qrcodes"
    os.makedirs(folder, exist_ok=True)

    file_path = f"{folder}/{product_id}.png"

    qr.save(file_path)

    return file_path