from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import *

# CustomUser Admin
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ['email', 'first_name', 'last_name', 'phone_number', 'is_verified', 'is_active', 'is_staff']
    list_filter = ['is_verified', 'is_active', 'is_staff']
    search_fields = ['email', 'first_name', 'last_name', 'phone_number']
    ordering = ['email']

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'phone_number', 'address')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'is_verified')}),
        ('Important Dates', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'phone_number', 'first_name', 'last_name', 'password1', 'password2', 'is_verified'),
        }),
    )

# Category Admin
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']

# FAQ Admin
@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ['question', 'answer', 'created_at']
    search_fields = ['question', 'answer']
    actions = ['add_sample_faqs']

    def add_sample_faqs(self, request, queryset):
        FAQ.objects.get_or_create(
            question='How do I return a product?',
            defaults={'answer': 'You can return a product within 30 days with the original receipt.'}
        )
        FAQ.objects.get_or_create(
            question='What are the shipping options?',
            defaults={'answer': 'We offer standard and express shipping across India.'}
        )
        self.message_user(request, "Added sample FAQs.")
    add_sample_faqs.short_description = "Add sample FAQs"

class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1   # Show 1 empty row by default

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1   # Show 1 empty row by default

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'price', 'is_new_drop']
    list_filter = ['category', 'is_new_drop', 'materials']
    search_fields = ['name', 'description']
    list_editable = ['price', 'is_new_drop']
    inlines = [ProductVariantInline, ProductImageInline]


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['user', 'created_at', 'updated_at']
    search_fields = ['user__email']


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ['cart', 'variant', 'quantity']
    search_fields = ['variant__product__name', 'cart__user__email']


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ['user', 'total_items', 'created_at', 'updated_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    filter_horizontal = ['products']  # Nice interface for many-to-many
    readonly_fields = ['created_at', 'updated_at', 'total_items']

    def total_items(self, obj):
        return obj.total_items
    total_items.short_description = 'Total Items'

@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ['wishlist_user', 'product', 'added_at']
    list_filter = ['added_at']
    search_fields = ['wishlist__user__email', 'product__name']
    
    def wishlist_user(self, obj):
        return obj.wishlist.user.email
    wishlist_user.short_description = 'User'


# # Category Admin
# @admin.register(Category)
# class CategoryAdmin(admin.ModelAdmin):
#     list_display = ['name', 'slug']
#     prepopulated_fields = {'slug': ('name',)}  # Auto-generate slug from name
#     search_fields = ['name']

# # Product Admin
# @admin.register(Product)
# class ProductAdmin(admin.ModelAdmin):
#     list_display = ['name', 'category', 'price', 'stock', 'is_new_drop']
#     list_filter = ['category', 'is_new_drop']
#     search_fields = ['name', 'description']
#     list_editable = ['price', 'stock', 'is_new_drop']
#     filter_horizontal = ['sizes', 'colors', 'materials']  # For JSON fields, use custom form if needed

# # Cart Admin
# @admin.register(Cart)
# class CartAdmin(admin.ModelAdmin):
#     list_display = ['user', 'created_at']
#     search_fields = ['user__email']

# # CartItem Admin
# @admin.register(CartItem)
# class CartItemAdmin(admin.ModelAdmin):
#     list_display = ['cart', 'product', 'quantity', 'size']
#     search_fields = ['product__name']

# # Wishlist Admin
# @admin.register(Wishlist)
# class WishlistAdmin(admin.ModelAdmin):
#     list_display = ['user']
#     filter_horizontal = ['products']

 # Order Admin
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
     list_display = ['order_id', 'user', 'status', 'total_amount', 'created_at']
     list_filter = ['status', 'created_at']
     search_fields = ['order_id', 'user__email']
     actions = ['mark_as_delivered']

     def mark_as_delivered(self, request, queryset):
         queryset.update(status='delivered')
         self.message_user(request, "Selected orders marked as delivered.")
     mark_as_delivered.short_description = "Mark selected orders as delivered"

 # OrderItem Admin
@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
     list_display = ['order', 'product', 'quantity', 'price', 'size']
     search_fields = ['product__name', 'order__order_id']

# # Review Admin
# @admin.register(Review)
# class ReviewAdmin(admin.ModelAdmin):
#     list_display = ['product', 'user', 'rating', 'created_at']
#     list_filter = ['rating', 'created_at']
#     search_fields = ['product__name', 'user__email']

# # FAQ Admin
# @admin.register(FAQ)
# class FAQAdmin(admin.ModelAdmin):
#     list_display = ['question', 'answer']
#     search_fields = ['question', 'answer']

# # OTP Admin
# @admin.register(OTP)
# class OTPAdmin(admin.ModelAdmin):
#     list_display = ['user', 'code', 'created_at', 'expires_at', 'is_valid']
#     list_filter = ['created_at', 'expires_at']
#     search_fields = ['user__email', 'code']

#     def is_valid(self, obj):
#         return obj.is_valid()
#     is_valid.boolean = True

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email', 'phone_number', 'created_at')
    search_fields = ('full_name', 'email')
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = [
        'code',
        'discount_type',
        'discount_value',
        'minimum_order_amount',
        'is_active',
        'valid_from',
        'valid_to',
        'usage_limit',
        'used_count',
        'is_currently_valid', # Custom method to show validity based on date and status
    ]
    list_filter = [
        'discount_type',
        'is_active',
        'valid_from',
        'valid_to',
    ]
    search_fields = ['code']
    readonly_fields = ['used_count'] # Prevent accidental modification of usage count via admin form
    fieldsets = (
        (None, {
            'fields': ('code', 'discount_type', 'discount_value', 'minimum_order_amount')
        }),
        ('Validity', {
            'fields': ('is_active', 'valid_from', 'valid_to'),
            'classes': ('collapse',) # Makes this section collapsible
        }),
        ('Usage', {
            'fields': ('usage_limit', 'used_count'),
            'classes': ('collapse',)
        }),
    )

    def is_currently_valid(self, obj):
        """Custom method to display if the coupon is valid based on date and status."""
        now = timezone.now()
        is_date_valid = obj.valid_from <= now <= obj.valid_to
        is_status_active = obj.is_active
        # Optionally, also check usage limit: is_usage_valid = obj.usage_limit is None or obj.used_count < obj.usage_limit
        return is_date_valid and is_status_active
    is_currently_valid.boolean = True # Shows a nice icon in the admin list view
    is_currently_valid.short_description = 'Currently Valid?' # Column header name

    # Optional: Add an action to mark selected coupons as inactive
    actions = ['mark_as_inactive']

    def mark_as_inactive(self, request, queryset):
        """Action to mark selected coupons as inactive."""
        updated_count = queryset.update(is_active=False)
        self.message_user(
            request,
            f"{updated_count} coupon(s) were successfully marked as inactive.",
            level='SUCCESS'
        )
    mark_as_inactive.short_description = "Mark selected coupons as inactive"