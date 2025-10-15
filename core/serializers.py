from rest_framework import serializers
from .models import *

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'first_name', 'last_name', 'email', 'phone_number', 'address']

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'



class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image']

class ProductVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = ['id', 'color', 'size', 'stock']

class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer()
    variants = ProductVariantSerializer(many=True, read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    is_wishlisted = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id',
            'name',
            'description',
            'price',
            'category',
            'materials',
            'is_new_drop',
            'variants',
            'images',
            'is_wishlisted',  # New field
        ]

    def get_is_wishlisted(self, obj):
        """Check if current user has this product in wishlist"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            try:
                wishlist = Wishlist.objects.get(user=request.user)
                return WishlistItem.objects.filter(
                    wishlist=wishlist, 
                    product=obj
                ).exists()
            except Wishlist.DoesNotExist:
                return False
        return False

class CartItemSerializer(serializers.ModelSerializer):
    variant = ProductVariantSerializer(read_only=True)
    variant_id = serializers.PrimaryKeyRelatedField(
        queryset=ProductVariant.objects.all(),
        source='variant',
        write_only=True
    )

    class Meta:
        model = CartItem
        fields = ['id', 'variant', 'variant_id', 'quantity']


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)

    class Meta:
        model = Cart
        fields = ['id', 'user', 'created_at', 'updated_at', 'items']

class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer()
    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'quantity', 'price', 'size']

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    class Meta:
        model = Order
        fields = ['id', 'order_id', 'user', 'total_amount', 'shipping_address', 'billing_email', 'status', 'created_at', 'items']

class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = ['id', 'question', 'answer', 'created_at', 'updated_at']

class WishlistItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source='product',
        write_only=True
    )
    
    class Meta:
        model = WishlistItem
        fields = ['id', 'product', 'product_id', 'added_at']

class WishlistSerializer(serializers.ModelSerializer):
    items = WishlistItemSerializer(many=True, read_only=True)
    total_items = serializers.ReadOnlyField()
    
    class Meta:
        model = Wishlist
        fields = ['id', 'user', 'total_items', 'created_at', 'updated_at', 'items']

class ContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = ['full_name', 'email', 'phone_number', 'message']
        # Optional: add extra validation
        extra_kwargs = {
            'phone_number': {'required': False, 'allow_blank': True, 'allow_null': True}
        }

    def validate_email(self, value):
        # Optional: add custom email validation
        if not value:
            raise serializers.ValidationError("Email is required.")
        return value

    def validate_full_name(self, value):
        if not value or len(value.strip()) < 2:
            raise serializers.ValidationError("Full name is required.")
        return value.strip()

    def validate_message(self, value):
        if not value or len(value.strip()) < 5:
            raise serializers.ValidationError("Message is too short.")
        return value.strip()

class CreateOrderSerializer(serializers.Serializer):
    amount = serializers.IntegerField(min_value=1)  # in paise
    # Optional: include cart items if you want to save them
    # items = serializers.ListField(child=serializers.DictField(), required=False)

    def validate_amount(self, value):
        if value % 100 != 0:
            # Optional: enforce ₹1, ₹2, etc. (not 50 paise)
            pass
        return value

class VerifyPaymentSerializer(serializers.Serializer):
    razorpay_order_id = serializers.CharField(max_length=100)
    razorpay_payment_id = serializers.CharField(max_length=100)
    razorpay_signature = serializers.CharField(max_length=200)

class CheckoutItemSerializer(serializers.Serializer):
    """
    Serializer for individual items fetched from the user's cart.
    Provides a summary for the checkout confirmation/order creation.
    """
    product_id = serializers.IntegerField(source='variant.product.id', read_only=True)
    product_name = serializers.CharField(source='variant.product.name', read_only=True)
    variant_id = serializers.IntegerField(source='variant.id', read_only=True)
    color = serializers.CharField(source='variant.color', read_only=True)
    size = serializers.CharField(source='variant.size', read_only=True)
    quantity = serializers.IntegerField(read_only=True)
    # Use the product's price from the variant's associated product
    price = serializers.DecimalField(source='variant.product.price', max_digits=10, decimal_places=2, read_only=True)
    total_price = serializers.SerializerMethodField()

    def get_total_price(self, obj):
        # obj is a CartItem instance
        # Calculate total for this cart item line (price * quantity)
        return float(obj.variant.product.price * obj.quantity)


# --- Main Serializer for Checkout Request ---
class CheckoutSerializer(serializers.Serializer):
    """
    Serializer for the checkout request body.
    Validates shipping details, payment method, and uses context to create the Order.
    """
    # Fields expected from the frontend request
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    email = serializers.EmailField() # Billing email

    # Shipping Address Fields (Based on Check out.pdf)
    address_line_1 = serializers.CharField(max_length=255) # Address
    address_line_2 = serializers.CharField(max_length=255, required=False, allow_blank=True) # Apartment, villa, etc. (Optional)
    city = serializers.CharField(max_length=100)
    state = serializers.CharField(max_length=100)
    pincode = serializers.CharField(max_length=20) # Pincode
    phone = serializers.CharField(max_length=15) # Phone number

    payment_method = serializers.ChoiceField(choices=Order.PAYMENT_METHOD_CHOICES, default='online')

    # Read-only field to show cart contents summary (useful for confirmation step or debugging)
    cart_items_summary = CheckoutItemSerializer(source='get_cart_items', many=True, read_only=True)

    # This method is primarily for read-only representation if needed in the output
    # The actual cart items are fetched in the view and passed via context
    def get_cart_items(self, obj):
        # This won't be called during input validation/deserialization
        # It's for output serialization if the full cart summary is returned
        # The cart items are accessed via self.context['cart_items'] in create()
        return [] # Placeholder for output logic if needed separately

    def create(self, validated_data):
        """
        Override create to handle order and order items creation based on context['cart_items'].
        """
        user = self.context['user']
        cart_items = self.context['cart_items']

        if not cart_items.exists():
             raise serializers.ValidationError("Cart is empty, cannot create order.")

        # --- Prepare Shipping Address String ---
        # Combine the individual address fields into the single TextField expected by your Order model
        address_parts = [
            validated_data['address_line_1'],
            validated_data.get('address_line_2', ''), # Use get with default empty string
            validated_data['city'],
            validated_data['state'],
            validated_data['pincode'],
            f"Phone: {validated_data['phone']}" # Include phone in the address string as shown in Check out.pdf
        ]
        full_shipping_address = ", ".join(part for part in address_parts if part)

        # --- Calculate Total Amount ---
        # Simple calculation based on cart item prices and quantities
        # Add logic here later for shipping cost, discounts, taxes if applicable before saving
        total_amount = sum(
            float(item.variant.product.price) * item.quantity for item in cart_items
        )

        # --- Create the Order Object ---
        order = Order.objects.create(
            user=user,
            # Combine name and address details into the shipping_address TextField
            shipping_address=full_shipping_address,
            # Use the email sent from the frontend as the billing email
            billing_email=validated_data['email'],
            payment_method=validated_data['payment_method'],
            total_amount=total_amount,
            # Status defaults to 'placed' as per your model
            # Other fields like razorpay_order_id will be set later
        )

        # --- Create OrderItem Objects based on CartItems ---
        for cart_item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=cart_item.variant.product, # Link to the Product
                variant=cart_item.variant,         # Link to the specific ProductVariant
                quantity=cart_item.quantity,
                # Store the price at the time of order (from the product)
                price=cart_item.variant.product.price,
                # Store the size explicitly (as per your OrderItem model)
                size=cart_item.variant.size
                # Color is implicitly linked via the variant
            )

        return order

    def validate(self, attrs):
        """
        Perform any cross-field validation if necessary.
        e.g., Check if billing email matches user's email if required.
        Currently, we just pass the validated data through.
        You could add validation for address format, phone number format, etc. here.
        """
        # Example: You *could* enforce email match if desired, but the frontend sends it explicitly
        # if attrs['email'] != self.context['user'].email:
        #     raise serializers.ValidationError("Billing email must match the user's registered email.")
        # For now, we accept the email sent from the frontend.

        # Example: Validate phone number format if needed (requires a custom validator or library)
        # phone = attrs.get('phone')
        # if not phone.isdigit() or len(phone) < 10: # Basic check
        #     raise serializers.ValidationError("Phone number is invalid.")

        return attrs # Return the validated attributes

# --- Example: Basic OrderSerializer for response (adjust fields as needed) ---
# You might already have a more detailed one.
class OrderSerializer(serializers.ModelSerializer):
    items = CheckoutItemSerializer(source='get_order_items', many=True, read_only=True) # Or a dedicated OrderItemSerializer
    user = serializers.StringRelatedField(read_only=True) # Show username

    class Meta:
        model = Order
        # Include fields relevant for the checkout confirmation response
        fields = [
            'id', 'order_id', 'user', 'status', 'total_amount',
            'shipping_address', 'billing_email', 'payment_method',
            'created_at', 'items' # Include the serialized items
        ]
        # Fields set by the backend or sensitive should be read-only
        read_only_fields = ['id', 'order_id', 'user', 'status', 'created_at']

    # If your Order model's 'items' related_name is 'items' (as in models.py),
    # this method is not strictly necessary for source='items'.
    # def get_order_items(self, obj):
    #     # This fetches OrderItems related to the Order instance (obj)
    #     return obj.items.all()

class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = '__all__'
        read_only_fields = ('used_count', 'created_at', 'updated_at') # Prevent modification of these via API

    def validate(self, data):
        """Add custom validation if needed."""
        valid_from = data.get('valid_from')
        valid_to = data.get('valid_to')
        if valid_from and valid_to and valid_from >= valid_to:
            raise serializers.ValidationError("Valid 'to' date must be after 'from' date.")
        return data