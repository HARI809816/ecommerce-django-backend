# core/utils/shipping.py
from decimal import Decimal

def calculate_shipping_cost(location: str, total_weight_kg: float) -> Decimal:
    """
    Calculate shipping cost based on location and total weight.
    Returns cost as Decimal (INR).
    """
    if not location:
        location = ""
    loc = location.strip().lower()

    # --- Free shipping for Chennai ---
    if "chennai" in loc or "tamil nadu" in loc:
        return Decimal('0.00')

    # --- Determine zone base rate ---
    surrounding_chennai = {"chengalpattu", "kanchipuram", "thiruvallur"}
    rest_tn = {
        "coimbatore", "madurai", "tiruchirappalli", "salem", "tirunelveli", "ariyalur",
        "cuddalore", "dharmapuri", "erode", "kallakurichi", "karur", "krishnagiri",
        "mayiladuthurai", "nagapattinam", "kanniyakumari", "namakkal", "perambalur",
        "pudukottai", "ramanathapuram", "ranipet", "sivagangai", "tenkasi", "thanjavur",
        "theni", "thiruvarur", "thoothukudi", "tirupathur", "tiruppur", "tiruvannamalai",
        "nilgiris", "vellore", "viluppuram", "virudhunagar"
    }
    nearby_states = {"karnataka", "kerala", "andhra", "telangana", "pondicherry", "puducherry"}

    if any(area in loc for area in surrounding_chennai):
        base_rate = Decimal('10.00')
    elif any(city in loc for city in rest_tn):
        base_rate = Decimal('20.00')
    elif any(state in loc for state in nearby_states):
        base_rate = Decimal('40.00')
    else:
        base_rate = Decimal('60.00')  # Rest of India

    # --- Weight surcharge ---
    if total_weight_kg <= 2.0:
        weight_surcharge = Decimal('0.00')
    elif total_weight_kg <= 5.0:
        weight_surcharge = Decimal('15.00')
    else:
        weight_surcharge = Decimal('30.00')

    return (base_rate + weight_surcharge).quantize(Decimal('0.01'))