# import qrcode
# import os

# def generate_qr(payment_id: str):

#     qr = qrcode.make()

#     folder = "static/qrcodes"
#     os.makedirs(folder, exist_ok=True)

#     file_path = f"{folder}/{payment_id}.png"

#     qr.save(file_path)

#     return file_path