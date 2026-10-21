"""Print VAPID keys to the administrator's terminal; do not share their private key."""
import base64
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
key=ec.generate_private_key(ec.SECP256R1())
enc=lambda b:base64.urlsafe_b64encode(b).decode().rstrip('=')
print('VAPID_PUBLIC_KEY='+enc(key.public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)))
print('VAPID_PRIVATE_KEY='+enc(key.private_numbers().private_value.to_bytes(32,'big')))
