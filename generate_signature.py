import hmac
import hashlib

# 👇 REPLACE THESE WITH YOUR VALUES
order_id = "order_RQ8UnIV3nJnfIq"      # ← from /create-order/ response
payment_id = "pay_TEST123456789"          # ← fake is OK
secret = "JyR1Q4jktP2M2cu1JZOsDNQc"  # ← from your .env file

signature = hmac.new(
    secret.encode(),
    f"{order_id}|{payment_id}".encode(),
    hashlib.sha256
).hexdigest()

print("✅ Use these in Postman:")
print(f"razorpay_order_id: {order_id}")
print(f"razorpay_payment_id: {payment_id}")
print(f"razorpay_signature: {signature}")