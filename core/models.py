from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from phonenumber_field.modelfields import PhoneNumberField
from django.core.exceptions import ValidationError
from decimal import Decimal
import uuid


class CustomUser(AbstractUser):
    email = models.EmailField(unique=True,null=True, blank=True)
    phone_number = PhoneNumberField(null=True, blank=True, unique=True)
    address = models.CharField(max_length=255, blank=True)
    is_verified = models.BooleanField(default=False)


    def __str__(self):
        return self.username
    
class Category(models.Model):
    name = models.CharField(max_length=100)  # e.g., 'Tracks', 'T-Shirts'
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey('Category', on_delete=models.CASCADE)
    materials = models.JSONField(default=list, blank=True)
    is_new_drop = models.BooleanField(default=False)

    def __str__(self):
        return self.name
    
class ProductVariant(models.Model):
    product = models.ForeignKey(Product, related_name="variants", on_delete=models.CASCADE)
    color = models.CharField(max_length=50)      # Example: Black, Blue
    size = models.CharField(max_length=10)       # Example: S, M, L
    stock = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.product.name} - {self.color} - {self.size}"

class ProductImage(models.Model):
    product = models.ForeignKey(Product, related_name="images", on_delete=models.CASCADE)
    image = models.ImageField(upload_to="products/")

    def __str__(self):
        return f"Image of {self.product.name}"
    
class Cart(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart of {self.user.email}"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('cart', 'variant')

    def __str__(self):
        return f"{self.quantity} x {self.variant.product.name} ({self.variant.color}, {self.variant.size})"

class Coupon(models.Model):
    DISCOUNT_TYPE_CHOICES = [
        ('percentage', 'Percentage'),
        ('fixed_amount', 'Fixed Amount'),
        ('bogo_50', 'BOGO 50% Off'),
    ]

    code = models.CharField(max_length=50, unique=True)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    minimum_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # For BOGO: link to specific products
    applicable_products = models.ManyToManyField(
        'Product',
        blank=True,
        help_text="Only used for BOGO-type coupons. Leave blank for site-wide coupons."
    )

    # ✅ NEW FIELD: New User Only Coupon
    is_new_user_only = models.BooleanField(
        default=False,
        help_text="If checked, this coupon can only be used by new users (users with no previous orders)."
    )

    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    used_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.code

    def clean(self):
        super().clean()
        if self.discount_type == 'percentage' and not (0 <= self.discount_value <= 100):
            raise ValidationError({'discount_value': 'Percentage must be between 0 and 100.'})
        if self.discount_type in ['fixed_amount', 'bogo_50'] and self.discount_value < 0:
            raise ValidationError({'discount_value': 'Discount value must be non-negative.'})
    
    def calculate_discount(self, total_amount):
        """Calculate discount amount based on discount type and value"""
        if self.discount_type == 'percentage':
            discount = total_amount * (self.discount_value / Decimal('100'))
            return min(discount, total_amount)  # Don't exceed total amount
        elif self.discount_type == 'fixed_amount':
            return min(self.discount_value, total_amount)  # Don't exceed total amount
        else:  # bogo_50 - this shouldn't be called directly for BOGO, handled separately
            return Decimal('0')
        

    def is_valid(self):
        from django.utils import timezone
        now = timezone.now()
        return (
            self.is_active
            and self.valid_from <= now <= self.valid_to
            and (self.usage_limit is None or self.used_count < self.usage_limit)
        )

    # ✅ NEW METHOD: Check if user is new
    def is_valid_for_user(self, user):
        """Check if coupon is valid for specific user (including new user check)"""
        if not self.is_valid():
            return False
        
        if self.is_new_user_only and user:
            # Check if user has any previous orders (excluding current order validation)
            from django.apps import apps
            Order = apps.get_model('core', 'Order')  # Replace with your app name
            previous_orders = Order.objects.filter(user=user).exclude(
                # Exclude orders that might be in validation process
                status='placed'  # or whatever status indicates pending validation
            ).count()
            
            if previous_orders > 0:
                return False
        
        return True
    
class Order(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('online', 'Online Payment'),
        ('cod', 'Cash on Delivery'),
    ]
    
    STATUS_CHOICES = [
        ('placed', 'Order Placed'),
        ('accepted', 'Accepted'),
        ('in_process', 'In Process'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    order_id = models.CharField(max_length=50, unique=True)
    razorpay_order_id = models.CharField(max_length=100, blank=True, null=True)
    payment_method = models.CharField(  # ✅ NEW FIELD
        max_length=10,
        choices=PAYMENT_METHOD_CHOICES,
        default='online'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='placed')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_address = models.TextField(blank=True)
    billing_email = models.EmailField(blank=True)
    applied_coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True) # Link to applied coupon
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0) # Store the applied discount amount

    def save(self, *args, **kwargs):
        if not self.order_id:
            self.order_id = f"ORD{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.order_id

class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey('ProductVariant', on_delete=models.CASCADE)  # No default, required
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    size = models.CharField(max_length=10)

    def __str__(self):
        return f"{self.quantity}x {self.product.name} ({self.size})"

class Payment(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    razorpay_payment_id = models.CharField(max_length=100)
    razorpay_signature = models.CharField(max_length=200)
    status = models.CharField(max_length=20, default='pending')  # pending, captured, failed
    created_at = models.DateTimeField(auto_now_add=True)

class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    rating = models.PositiveIntegerField(default=1)  # 1-5
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class FAQ(models.Model):
    question = models.CharField(max_length=200)
    answer = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.question

# For OTP verification (simple model, expire after use)
from django.db import models
from django.utils import timezone

class OTP(models.Model):
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="otps"   # ✅ Add reverse relation
    )   
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    def is_valid(self):
        """Check if OTP is still valid and unused"""
        return not self.is_used and timezone.now() < self.expires_at

    def __str__(self):
        return f"OTP for {self.user.email} - {self.code}"

class Wishlist(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='wishlist')
    products = models.ManyToManyField(Product, blank=True, related_name='wishlisted_by')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Wishlist of {self.user.email}"

    @property
    def total_items(self):
        return self.products.count()

class WishlistItem(models.Model):
    """Alternative approach using through model for more control"""
    wishlist = models.ForeignKey(Wishlist, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('wishlist', 'product')

    def __str__(self):
        return f"{self.product.name} in {self.wishlist.user.email}'s wishlist"
    

class ContactMessage(models.Model):
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} <{self.email}>"

    class Meta:
        verbose_name = "Contact Message"
        verbose_name_plural = "Contact Messages"

