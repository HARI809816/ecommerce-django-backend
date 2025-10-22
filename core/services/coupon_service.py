# core/services/coupon_service.py

from decimal import Decimal
from collections import defaultdict

def apply_coupon_to_cart(coupon, cart_items, user=None):  # ✅ ADD USER PARAMETER
    """
    Apply coupon to cart items and return discount amount.
    Supports 'bogo_50', 'percentage', and 'fixed_amount'.
    """
    # ✅ CHECK NEW USER VALIDATION
    if hasattr(coupon, 'is_new_user_only') and coupon.is_new_user_only:
        if not user or not coupon.is_valid_for_user(user):
            return Decimal('0')
    
    if not coupon.is_valid():
        return Decimal('0')

    if coupon.discount_type == 'bogo_50':
        return _apply_bogo_50(coupon, cart_items)
    else:
        # For non-BOGO, this function isn't used — handled via order total elsewhere
        return Decimal('0')


def _apply_bogo_50(coupon, cart_items):
    discount = Decimal('0')
    applicable_product_ids = set(coupon.applicable_products.values_list('id', flat=True))

    per_unit_prices = defaultdict(list)
    for item in cart_items:
        if item.variant.product_id in applicable_product_ids:
            price = Decimal(str(item.variant.product.price))
            for _ in range(item.quantity):
                per_unit_prices[item.variant.product_id].append(price)

    for product_id, prices in per_unit_prices.items():
        prices.sort()  # cheapest first
        # Apply 50% off on every 2nd item (index 1, 3, 5...)
        for i in range(1, len(prices), 2):
            discount += prices[i] * Decimal('0.5')

    return discount