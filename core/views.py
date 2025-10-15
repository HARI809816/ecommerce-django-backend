from django.shortcuts import render
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework import permissions
from rest_framework.views import APIView
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.crypto import get_random_string
from datetime import timedelta
from rest_framework.authtoken.models import Token
from rest_framework import viewsets
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import FAQ, Order, Product, CartItem, Cart, OrderItem, ProductVariant, Payment, Category, Wishlist, WishlistItem, Coupon
from .serializers import FAQSerializer, OrderSerializer, ProductSerializer, CartItemSerializer, CartSerializer, ContactMessageSerializer, CreateOrderSerializer, VerifyPaymentSerializer, CategorySerializer, CheckoutItemSerializer, CheckoutSerializer 
from .filters import ProductFilter 
from .models import CustomUser, OTP, ContactMessage
from django.contrib.auth import get_user_model
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from phonenumber_field.phonenumber import PhoneNumber
from django.db.models import Q
from django.db import transaction
import razorpay
from decouple import config
import hmac
import hashlib
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import authentication_classes, permission_classes
from decimal import Decimal
from core.services.coupon_service import apply_coupon_to_cart
from decimal import Decimal, InvalidOperation
from .utils.shipping import calculate_shipping_cost


razorpay_client = razorpay.Client(
    auth=(config('RAZORPAY_KEY_ID'), config('RAZORPAY_KEY_SECRET'))
)


class SignupView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = (request.data.get("email") or "").strip().lower()
        phone = (request.data.get("phone_number") or "").strip()
        terms_accepted = request.data.get("terms_accepted")

        # ✅ Must provide either email or phone, not both
        if not email and not phone:
            return Response(
                {"error": "Provide either email OR phone number"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if email and phone:
            return Response(
                {"error": "Provide only one field: email OR phone number"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ✅ For NEW signups only: terms must be accepted
        # We don't require terms for existing users (login flow)
        is_new_user = False
        try:
            # Check if user exists → login flow
            if email:
                user = CustomUser.objects.get(email=email)
            else:
                user = CustomUser.objects.get(phone_number=phone)
        except CustomUser.DoesNotExist:
            is_new_user = True
            # 🔒 Require terms acceptance for new users
            if not terms_accepted or str(terms_accepted).lower() not in ['true', '1', 'yes']:
                return Response(
                    {"error": "You must accept the Terms and Conditions to sign up."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # ✅ Create new user
            user = CustomUser.objects.create(
                email=email if email else None,
                phone_number=phone if phone else None,
                username=email if email else phone,
                is_verified=False,
            )
            user.set_unusable_password()
            user.save()

        # Generate OTP (same for login or signup)
        otp_code = get_random_string(length=6, allowed_chars="1234567890")
        expires_at = timezone.now() + timedelta(minutes=5)
        OTP.objects.create(user=user, code=otp_code, expires_at=expires_at)
        print(f"Generated OTP for {'signup' if is_new_user else 'login'}: {otp_code}")  # For debugging; remove in production

        # Send OTP
        if email:
            send_mail(
                "Your OTP Code",
                f"Your OTP code is {otp_code}. It will expire in 5 minutes.",
                None,
                [email],
            )
        else:
            send_otp_sms(phone, otp_code)

        if is_new_user:
            return Response(
                {"message": "Signup successful. OTP sent for verification"},
                status=status.HTTP_200_OK,
            )
        else:
            return Response(
                {"message": "User already exists. Login OTP sent successfully"},
                status=status.HTTP_200_OK,
            )


class VerifyOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        code = request.data.get('otp')

        if not code:
            return Response(
                {'error': 'OTP is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Strip whitespace and ensure string
        code = str(code).strip()

        try:
            # Find the latest unused OTP with this code
            otp = OTP.objects.select_related('user').filter(
                code=code,
                is_used=False
            ).latest('created_at')

        except OTP.DoesNotExist:
            return Response(
                {'error': 'Invalid OTP'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check expiration
        if timezone.now() > otp.expires_at:
            return Response(
                {'error': 'OTP has expired'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get user from OTP
        user = otp.user

        # Mark user as verified
        user.is_verified = True
        user.save()

        # Mark OTP as used
        otp.is_used = True
        otp.save()

        # Create or get auth token
        token, _ = Token.objects.get_or_create(user=user)

        return Response({
            'token': token.key,
            'message': 'Verification successful'
        }, status=status.HTTP_200_OK)
    

class CompleteProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]  # ✅ only logged-in users

    def post(self, request):
        first_name = (request.data.get("first_name") or "").strip()
        last_name = (request.data.get("last_name") or "").strip()

        if not first_name:
            return Response(
                {"error": "First name is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ✅ Update current user profile
        user = request.user
        user.first_name = first_name
        user.last_name = last_name
        user.username = first_name  # 👈 overwrite username with first_name
        user.save()

        return Response(
            {
                "message": "Profile completed successfully",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    'phone_number': str(user.phone_number) if user.phone_number else None,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                },
            },
            status=status.HTTP_200_OK,
        )
    
User = get_user_model()  # This will be your CustomUser

@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    if request.method == 'GET':
        return Response({
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'email': request.user.email,
            'phone_number': str(request.user.phone_number) if request.user.phone_number else "",
            'address': request.user.address,
        })

    elif request.method == 'PUT':
        data = request.data
        user = request.user

        # Get new values
        new_email = data.get('email', user.email)
        new_phone = data.get('phone_number', None)  # could be empty string

        # ✅ Validate email uniqueness (skip if unchanged)
        if new_email and new_email != user.email:
            if CustomUser.objects.filter(email=new_email).exists():
                return Response(
                    {"error": "This email is already in use."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # ✅ Validate phone uniqueness (skip if unchanged or empty)
        if new_phone and new_phone != str(user.phone_number):
            # Normalize phone to E.164
            try:
                phone_obj = PhoneNumber.from_string(new_phone)
                if not phone_obj.is_valid():
                    return Response(
                        {"error": "Invalid phone number."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                normalized_phone = str(phone_obj)
            except Exception:
                return Response(
                    {"error": "Invalid phone number format."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if CustomUser.objects.filter(phone_number=normalized_phone).exists():
                return Response(
                    {"error": "This phone number is already in use."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            user.phone_number = normalized_phone
        elif new_phone == "":
            user.phone_number = None

        # Update other fields
        user.first_name = data.get('first_name', user.first_name)
        user.last_name = data.get('last_name', user.last_name)
        user.address = data.get('address', user.address)
        user.email = new_email  # safe now

        try:
            user.save()
            return Response({'message': 'Profile updated successfully'})
        except Exception as e:
            return Response(
                {"error": "Failed to update profile. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = (request.data.get("email") or "").strip()
        phone = (request.data.get("phone_number") or "").strip()

        # Ensure at least one field is provided
        if not email and not phone:
            return Response(
                {"error": "Provide either email OR phone number"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # ✅ Priority: email first, then phone
            if email:
                user = CustomUser.objects.get(email__iexact=email)
                print(f"Found user by email: {user.email}")
            else:
                user = CustomUser.objects.get(phone_number__iexact=phone)
                print(f"Found user by phone: {user.phone_number}")

            # ✅ Check if signup OTP verified
            if not user.is_verified:
                return Response(
                    {"error": "User not verified (signup OTP not completed)"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # ✅ Generate OTP
            otp_code = get_random_string(length=6, allowed_chars="1234567890")
            expires_at = timezone.now() + timedelta(minutes=5)
            OTP.objects.create(user=user, code=otp_code, expires_at=expires_at)
           # print(f"Generated Login OTP for {user.email}: {otp_code}")  # For debugging; remove in production
            # ✅ Send OTP via email
            if email:
                send_mail(
                    "Your Login OTP Code",
                    f"Your OTP code is {otp_code}. It will expire in 5 minutes.",
                    None,  # Uses DEFAULT_FROM_EMAIL from settings.py
                    [user.email],
                    fail_silently=False,
                )
            else:
                print(f"Sending OTP to phone number: {user.phone_number}")
                send_otp_sms(user.phone_number, otp_code)


            return Response({"message": "Login OTP sent successfully"}, status=status.HTTP_200_OK)

        except CustomUser.DoesNotExist:
            return Response(
                {"error": "Invalid credentials"},
                status=status.HTTP_400_BAD_REQUEST,
            )


             
from twilio.rest import Client
from django.conf import settings

def send_otp_sms(phone_number, otp_code):
    """
    Sends OTP SMS using Twilio.
    phone_number: recipient in E.164 format, e.g., +91812470XXXX
    otp_code: the OTP string
    """
    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            body=f"Your OTP code is {otp_code}. It will expire in 5 minutes.",
            from_=settings.TWILIO_PHONE_NUMBER,
            to=str(phone_number)
        )
        print(f"✅ SMS sent successfully")
        print(f"From: {settings.TWILIO_PHONE_NUMBER}, To: {phone_number}, SID: {message.sid}")
        return True
    except Exception as e:
        # Print full error details for debugging
        print("❌ Failed to send SMS:")
        print(f"From: {settings.TWILIO_PHONE_NUMBER}, To: {phone_number}")
        print(str(e))
        return False
    

class ChangeContactView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        old_email = (request.data.get("old_email") or "").strip().lower()
        old_phone = (request.data.get("old_phone") or "").strip()
        new_email = (request.data.get("new_email") or "").strip().lower()
        new_phone = (request.data.get("new_phone") or "").strip()

        # Ensure at least one field is provided
        if not (old_email or old_phone):
            return Response(
                {"error": "Provide old email or old phone"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not (new_email or new_phone):
            return Response(
                {"error": "Provide new email or new phone"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Find the user by old email/phone
            if old_email:
                user = CustomUser.objects.get(email__iexact=old_email)
            else:
                user = CustomUser.objects.get(phone_number__iexact=old_phone)

            # Update contact info
            if new_email:
                if CustomUser.objects.filter(email=new_email).exists():
                    return Response({"error": "Email already exists"}, status=400)
                user.email = new_email
            if new_phone:
                if CustomUser.objects.filter(phone_number=new_phone).exists():
                    return Response({"error": "Phone already exists"}, status=400)
                user.phone_number = new_phone

            user.save()

            # Invalidate previous OTPs
            OTP.objects.filter(user=user, is_used=False).update(is_used=True)

            # Generate and send new OTP
            otp_code = get_random_string(length=6, allowed_chars="1234567890")
            expires_at = timezone.now() + timedelta(minutes=5)
            OTP.objects.create(user=user, code=otp_code, expires_at=expires_at)
            print(f"Generated OTP for contact change: {otp_code}")  # For debugging; remove in production

            if new_email:
                send_mail(
                    "Your New OTP Code",
                    f"Your new OTP code is {otp_code}. It will expire in 5 minutes.",
                    None,
                    [new_email],
                    fail_silently=False,
                )
            elif new_phone:
                send_otp_sms(new_phone, otp_code)

            return Response({"message": "Contact updated and new OTP sent"}, status=200)

        except CustomUser.DoesNotExist:
            return Response({"error": "User not found"}, status=404)

class ResendOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = (request.data.get("email") or "").strip().lower()
        phone = (request.data.get("phone_number") or "").strip()

        # ✅ Require either email or phone
        if not email and not phone:
            return Response(
                {"error": "Provide email OR phone number"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # ✅ Find existing user
            if email:
                user = CustomUser.objects.get(email__iexact=email)
            else:
                user = CustomUser.objects.get(phone_number__iexact=phone)

            # ✅ Prevent spamming: check cooldown
            last_otp = OTP.objects.filter(user=user).order_by("-created_at").first()
            if last_otp and (timezone.now() - last_otp.created_at).seconds < 30:
                remaining = 30 - (timezone.now() - last_otp.created_at).seconds
                return Response(
                    {"error": f"Please wait {remaining} seconds before requesting a new OTP"},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

            # ✅ Invalidate old OTPs
            OTP.objects.filter(user=user, is_used=False).update(is_used=True)

            # ✅ Generate new OTP
            otp_code = get_random_string(length=6, allowed_chars="1234567890")
            expires_at = timezone.now() + timedelta(minutes=5)
            OTP.objects.create(user=user, code=otp_code, expires_at=expires_at)

            # ✅ Send OTP
            if email:
                send_mail(
                    "Your OTP Code",
                    f"Your OTP code is {otp_code}. It will expire in 5 minutes.",
                    None,
                    [user.email],
                )
            else:
                send_otp_sms(user.phone_number, otp_code)

            # ✅ Response message depends on whether user is verified
            if user.is_verified:
                msg = "Login OTP resent successfully"
            else:
                msg = "Signup OTP resent successfully"

            return Response({"message": msg}, status=status.HTTP_200_OK)

        except CustomUser.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        
        
class FAQViewSet(viewsets.ModelViewSet):
    queryset = FAQ.objects.all()
    serializer_class = FAQSerializer
    permission_classes = [AllowAny]  # Public access for FAQs

class OrderTrackingView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        order_id = request.data.get('order_id')
        billing_email = request.data.get('billing_email')

        if not order_id or not billing_email:
            return Response({'error': 'Order ID and billing email are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = Order.objects.get(order_id=order_id, billing_email=billing_email, user=request.user)
            serializer = OrderSerializer(order)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found or access denied'}, status=status.HTTP_404_NOT_FOUND)
        
class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]
    # Keep SearchFilter and OrderingFilter for name/description search and basic price/name ordering
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend, ] # Removed DjangoFilterBackend if not directly used

    filterset_class = ProductFilter   # ← Link your custom filter
    search_fields = ['name', 'description']
    ordering_fields = ['price', 'name', 'id'] # Add 'id' for default ordering if needed
    ordering = ['id'] # Default ordering, e.g., by creation ID

    def get_serializer_context(self):
        """Pass request context to serializer"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def get_queryset(self):
        queryset = super().get_queryset()

        # --- Filter Logic Based on PDF ---

        # 1. Filter by Size (from ProductVariant)
        size = self.request.query_params.get('size')
        if size:
            # Filter products that have at least one variant matching the size
            # Use iexact for case-insensitive match if needed, adjust based on your data format
            queryset = queryset.filter(variants__size__iexact=size).distinct()

        # 2. Filter by Color (from ProductVariant)
        color = self.request.query_params.get('color')
        if color:
            # Filter products that have at least one variant matching the color
            # Use iexact for case-insensitive match if needed, adjust based on your data format
            queryset = queryset.filter(variants__color__iexact=color).distinct()

        # 3. Filter by Material (from Product.materials JSON field)
        material = self.request.query_params.get('material')
        if material:
            # Filter products where the materials JSON array contains the specified material
            # Using __contains for JSON fields. Ensure your DB supports this (PostgreSQL, MySQL 5.7+, SQLite with json1 extension)
            # The material name in the query param should match exactly one item in the JSON array.
            # For case-insensitive matching, you might need a database-specific function or a different approach.
            # For now, assuming exact match within the array is sufficient.
            # Example: if material='cotton', it matches products where materials contains 'cotton'.
            queryset = queryset.filter(materials__contains=[material.lower()]) # Use lower() if your stored materials are lowercase

        # 4. Filter by Price Range
        # Handle specific price ranges like "Under 1000", "Under 500", "Under 2000"
        price_under = self.request.query_params.get('price_under')
        if price_under:
            try:
                max_price = int(price_under)
                queryset = queryset.filter(price__lte=max_price)
            except ValueError:
                # Optionally log or handle invalid price_under value
                pass # Silently ignore invalid input, or return an error response

        # Handle min/max price range (could be used alongside or instead of 'price_under')
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')
        if min_price:
            try:
                min_p = int(min_price)
                queryset = queryset.filter(price__gte=min_p)
            except ValueError:
                pass # Silently ignore invalid input, or return an error response
        if max_price:
            try:
                max_p = int(max_price)
                queryset = queryset.filter(price__lte=max_p)
            except ValueError:
                pass # Silently ignore invalid input, or return an error response

        # 5. Filter by Category (if needed, already present in original code)
        category_slug = self.request.query_params.get('category')
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)


        # --- Sorting Logic Based on PDF ---
        # The `filters.OrderingFilter` handles 'ordering' query param like ?ordering=price, ?ordering=-price, ?ordering=name
        # Default ordering is set in `ordering = ['id']`
        # Common query params would be:
        # ?ordering=price (Low to High) - Uses the 'price' field on Product
        # ?ordering=-price (High to Low)
        # ?ordering=name
        # ?ordering=-name

        sort_by = self.request.query_params.get('sort_by')
        if sort_by == 'popular':
            # Example sorting by popularity based on OrderItem count (requires OrderItem to link to Product)
            # Adjust related_name if necessary (e.g., if OrderItem links to ProductVariant, it's more complex)
            # Assuming OrderItem has 'product' field linking directly to Product (as per models.py)
            # This might be performance-intensive without proper indexing
            queryset = queryset.annotate(
                num_orders=Count('items') # 'items' is the related_name from Order to OrderItem
            ).order_by('-num_orders')

        elif sort_by == 'trending':
            # Trending is often based on recent activity.
            # A simple proxy could be recent creation (using default ordering) or recent orders.
            # For a more dynamic trend, you'd need a backend job calculating scores.
            # For now, let's just keep the default ordering or apply a recent order filter if available.
            # Default ordering 'id' often implies recent creation.
            # Or, sort by recent orders (e.g., orders created in the last N days)
            # This requires joining with Order and OrderItem and filtering by date.
            # For simplicity here, we'll just keep the default or apply a placeholder if needed.
            # Default ordering often implies recency, which is a basic trend indicator.
            # Example placeholder: order by default (or by a hypothetical recent_activity_score)
            # queryset = queryset.order_by('-recent_activity_score') # Requires such a field
            # For now, just pass (use default or ordering filter)
            pass # Keeps default or applies ?ordering=... if present

        # The standard ?ordering=... parameter is handled by filters.OrderingFilter
        # based on the 'ordering_fields' defined above.

        return queryset.distinct() # Ensure distinct results if joins were made via variants



class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Users can only see their own orders
        return self.queryset.filter(user=self.request.user)


class CartViewSet(viewsets.ViewSet):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_cart(self, user):
        cart, created = Cart.objects.get_or_create(user=user)
        return cart

    def list(self, request):
        cart = self.get_cart(request.user)
        serializer = CartSerializer(cart)
        return Response(serializer.data)

    def create(self, request):
        cart = self.get_cart(request.user)
        serializer = CartItemSerializer(data=request.data)
        if serializer.is_valid():
            variant = serializer.validated_data['variant']
            quantity = serializer.validated_data['quantity']

            # Check stock
            if quantity > variant.stock:
                return Response(
                    {"error": f"Only {variant.stock} left for {variant.product.name} {variant.size} ({variant.color})"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Add or update cart item
            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                variant=variant,
                defaults={'quantity': quantity}
            )
            if not created:
                cart_item.quantity += quantity
                if cart_item.quantity > variant.stock:
                    return Response(
                        {"error": f"Only {variant.stock} left for {variant.product.name}"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                cart_item.save()

            return Response(CartItemSerializer(cart_item).data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, pk=None):
        cart = self.get_cart(request.user)
        try:
            cart_item = cart.items.get(pk=pk)
            cart_item.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except CartItem.DoesNotExist:
            return Response({'error': 'Cart item not found'}, status=status.HTTP_404_NOT_FOUND)
        

from .models import Wishlist, WishlistItem
from .serializers import WishlistSerializer, WishlistItemSerializer

class WishlistViewSet(viewsets.ViewSet):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_wishlist(self, user):
        """Get or create wishlist for user"""
        wishlist, created = Wishlist.objects.get_or_create(user=user)
        return wishlist

    def list(self, request):
        """Get user's wishlist"""
        wishlist = self.get_wishlist(request.user)
        serializer = WishlistSerializer(wishlist)
        return Response(serializer.data)

    def create(self, request):
        """Add product to wishlist"""
        wishlist = self.get_wishlist(request.user)
        product_id = request.data.get('product_id')
        
        if not product_id:
            return Response(
                {"error": "Product ID is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response(
                {"error": "Product not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if product already in wishlist
        wishlist_item, created = WishlistItem.objects.get_or_create(
            wishlist=wishlist,
            product=product
        )
        
        if created:
            serializer = WishlistItemSerializer(wishlist_item)
            return Response(
                {
                    "message": "Product added to wishlist",
                    "item": serializer.data
                },
                status=status.HTTP_201_CREATED
            )
        else:
            return Response(
                {"message": "Product already in wishlist"},
                status=status.HTTP_200_OK
            )

    def destroy(self, request, pk=None):
        """Remove product from wishlist"""
        wishlist = self.get_wishlist(request.user)
        
        try:
            # pk can be either wishlist_item_id or product_id
            try:
                # First try to find by wishlist item ID
                wishlist_item = WishlistItem.objects.get(
                    id=pk,
                    wishlist=wishlist
                )
            except WishlistItem.DoesNotExist:
                # If not found, try to find by product ID
                wishlist_item = WishlistItem.objects.get(
                    product_id=pk,
                    wishlist=wishlist
                )
            
            product_name = wishlist_item.product.name
            wishlist_item.delete()
            
            return Response(
                {"message": f"{product_name} removed from wishlist"},
                status=status.HTTP_200_OK
            )
            
        except WishlistItem.DoesNotExist:
            return Response(
                {"error": "Product not found in wishlist"},
                status=status.HTTP_404_NOT_FOUND
            )

class ToggleWishlistView(APIView):
    """Alternative view to toggle wishlist items"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        product_id = request.data.get('product_id')
        
        if not product_id:
            return Response(
                {"error": "Product ID is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response(
                {"error": "Product not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        wishlist, created = Wishlist.objects.get_or_create(user=request.user)
        
        try:
            wishlist_item = WishlistItem.objects.get(
                wishlist=wishlist,
                product=product
            )
            # Product exists in wishlist, remove it
            wishlist_item.delete()
            return Response(
                {
                    "message": f"{product.name} removed from wishlist",
                    "in_wishlist": False
                },
                status=status.HTTP_200_OK
            )
        except WishlistItem.DoesNotExist:
            # Product not in wishlist, add it
            WishlistItem.objects.create(
                wishlist=wishlist,
                product=product
            )
            return Response(
                {
                    "message": f"{product.name} added to wishlist",
                    "in_wishlist": True
                },
                status=status.HTTP_201_CREATED
            )

class CheckWishlistView(APIView):
    """Check if products are in user's wishlist"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        product_ids = request.data.get('product_ids', [])
        
        if not product_ids or not isinstance(product_ids, list):
            return Response(
                {"error": "product_ids array is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            wishlist = Wishlist.objects.get(user=request.user)
            wishlist_product_ids = list(
                WishlistItem.objects.filter(
                    wishlist=wishlist,
                    product_id__in=product_ids
                ).values_list('product_id', flat=True)
            )
            
            result = {}
            for product_id in product_ids:
                result[str(product_id)] = product_id in wishlist_product_ids
                
            return Response(result, status=status.HTTP_200_OK)
            
        except Wishlist.DoesNotExist:
            # User has no wishlist, so nothing is wishlisted
            result = {str(pid): False for pid in product_ids}
            return Response(result, status=status.HTTP_200_OK)
        

@api_view(['POST'])
@permission_classes([AllowAny])
def contact_us(request):
    serializer = ContactMessageSerializer(data=request.data)
    
    if serializer.is_valid():
        serializer.save()  # Saves to DB
        return Response({
            "message": "Thank you for contacting us. We'll get back to you soon!",
            #"id" :   # optional
        }, status=status.HTTP_201_CREATED)
    
    # Return validation errors
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def place_order(request):
    user = request.user
    data = request.data

    # Validate top-level fields
    shipping_address = data.get('shipping_address')
    billing_email = data.get('billing_email')
    items = data.get('items', [])

    if not shipping_address:
        return Response({"error": "Shipping address is required"}, status=400)
    if not billing_email:
        return Response({"error": "Billing email is required"}, status=400)
    if not items:
        return Response({"error": "At least one item is required"}, status=400)

    try:
        with transaction.atomic():  # Ensure all-or-nothing
            # Create order
            order = Order.objects.create(
                user=user,
                shipping_address=shipping_address,
                billing_email=billing_email,
                total_amount=0,
                status='placed'
            )

            total = 0
            for item_data in items:
                variant_id = item_data.get('variant_id')
                quantity = item_data.get('quantity', 1)

                if not variant_id:
                    raise ValueError("variant_id is required for each item")

                # Get variant and lock it for update (prevent race condition)
                variant = ProductVariant.objects.select_for_update().get(id=variant_id)

                if variant.stock < quantity:
                    raise ValueError(f"Not enough stock for {variant.product.name} (Size: {variant.size}, Color: {variant.color})")

                # Create order item
                OrderItem.objects.create(
                    order=order,
                    product=variant.product,
                    variant=variant,
                    quantity=quantity,
                    price=variant.product.price,  # Use current product price
                    size=variant.size
                )
                total += float(variant.product.price) * quantity

                # Reduce stock
                variant.stock -= quantity
                variant.save()

            # Update total
            order.total_amount = total
            order.save()

            # Return response
            serializer = OrderSerializer(order)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

    except ProductVariant.DoesNotExist:
        return Response({"error": "Invalid variant_id"}, status=400)
    except ValueError as e:
        return Response({"error": str(e)}, status=400)
    except Exception as e:
        return Response({"error": "Failed to place order. Please try again."}, status=500)
    

class CreateOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            coupon_code = request.data.get('coupon_code', '').strip()

            # Get user's cart
            cart = Cart.objects.get(user=request.user)
            cart_items = cart.items.select_related('variant__product').all()
            
            if not cart_items.exists():
                return Response(
                    {"error": "Cart is empty"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Calculate base total
            total = sum(
                Decimal(str(item.variant.product.price)) * item.quantity 
                for item in cart_items
            )

            # Apply coupon
            discount_amount = Decimal('0')
            applied_coupon = None

            if coupon_code:
                try:
                    coupon = Coupon.objects.get(code=coupon_code, is_active=True)
                    if coupon.is_valid():
                        if coupon.discount_type == 'bogo_50':
                            discount_amount = apply_coupon_to_cart(coupon, list(cart_items))
                        else:
                            if total >= coupon.minimum_order_amount:
                                discount_amount = coupon.calculate_discount(total)
                        if discount_amount > 0:
                            applied_coupon = coupon
                            coupon.used_count += 1
                            coupon.save(update_fields=['used_count'])
                except Coupon.DoesNotExist:
                    return Response(
                        {"error": "Invalid coupon code"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            final_total = total - discount_amount
            # Convert to paise for Razorpay (INR: ₹1 = 100 paise)
            amount_in_paise = int(final_total * 100)

            # Create Razorpay order
            razorpay_order = razorpay_client.order.create({
                "amount": amount_in_paise,
                "currency": "INR",
                "payment_capture": 1,
            })

            # Build shipping address (same as COD)
            user = request.user
            address_parts = [
                user.address or "Address not provided",
                f"Phone: {user.phone_number}" if hasattr(user, 'phone_number') else ""
            ]
            shipping_address = ", ".join(part for part in address_parts if part)

            # Create order (but don't clear cart yet — wait for payment verification)
            order = Order.objects.create(
                user=request.user,
                total_amount=final_total,
                discount_amount=discount_amount,
                applied_coupon=applied_coupon,
                payment_method='online',
                shipping_address=shipping_address,
                billing_email=user.email,
                razorpay_order_id=razorpay_order['id'],
                status='placed'
            )

            # Create OrderItems
            for item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product=item.variant.product,
                    variant=item.variant,
                    quantity=item.quantity,
                    price=item.variant.product.price,
                    size=item.variant.size
                )

            return Response({
                "razorpay_order_id": razorpay_order['id'],
                "amount": amount_in_paise,
                "currency": "INR",
                "order_id": order.order_id,
                "total_amount": str(final_total),
                "discount_applied": str(discount_amount)
            }, status=status.HTTP_201_CREATED)

        except Cart.DoesNotExist:
            return Response({"error": "Cart not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"error": "Failed to create order", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

@method_decorator(csrf_exempt, name='dispatch')
class VerifyPaymentView(APIView):
    """
    Verify Razorpay payment signature and record payment in DB.
    Expects:
    {
      "razorpay_order_id": "order_...",
      "razorpay_payment_id": "pay_...",
      "razorpay_signature": "..."
    }
    """
    def post(self, request):
        serializer = VerifyPaymentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        order_id = data['razorpay_order_id']
        payment_id = data['razorpay_payment_id']
        signature = data['razorpay_signature']

        # Verify signature using Razorpay secret
        secret = config('RAZORPAY_KEY_SECRET')
        generated_signature = hmac.new(
            secret.encode(),
            f"{order_id}|{payment_id}".encode(),
            hashlib.sha256
        ).hexdigest()

        if generated_signature != signature:
            return Response(
                {"error": "Invalid payment signature"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Find the order
            order = Order.objects.get(razorpay_order_id=order_id)

            # Save payment record
            Payment.objects.create(
                order=order,
                razorpay_payment_id=payment_id,
                razorpay_signature=signature,
                status='captured'
            )

            # Optional: update order status
            order.payment_status = 'paid'
            order.save()

            return Response({
                "status": "success",
                "message": "Payment verified and saved successfully"
            }, status=status.HTTP_200_OK)

        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": "Failed to save payment record", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
class CreateCODOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            coupon_code = request.data.get('coupon_code', '').strip()

            cart = Cart.objects.get(user=request.user)
            cart_items = cart.items.select_related('variant__product').all()
            
            if not cart_items.exists():
                return Response(
                    {"error": "Cart is empty"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Calculate base total
            total = sum(
                Decimal(str(item.variant.product.price)) * item.quantity 
                for item in cart_items
            )

            # Initialize discount & coupon
            discount_amount = Decimal('0')
            applied_coupon = None

            # Apply coupon if provided
            if coupon_code:
                try:
                    coupon = Coupon.objects.get(code=coupon_code, is_active=True)
                    if coupon.is_valid():
                        if coupon.discount_type == 'bogo_50':
                            discount_amount = apply_coupon_to_cart(coupon, list(cart_items))
                        else:
                            # Handle percentage/fixed on order total
                            if total >= coupon.minimum_order_amount:
                                discount_amount = coupon.calculate_discount(total)
                            else:
                                discount_amount = Decimal('0')
                        
                        if discount_amount > 0:
                            applied_coupon = coupon
                            coupon.used_count += 1
                            coupon.save(update_fields=['used_count'])
                    # If invalid, ignore silently or raise error (here: ignore)
                except Coupon.DoesNotExist:
                    return Response(
                        {"error": "Invalid coupon code"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            final_total = total - discount_amount

            shipping_address = request.user.address or "Address not provided"
            billing_email = request.user.email or ""

            # Create order
            order = Order.objects.create(
                user=request.user,
                total_amount=final_total,
                discount_amount=discount_amount,      # ✅ Saved
                applied_coupon=applied_coupon,        # ✅ Linked
                payment_method='cod',
                shipping_address=shipping_address,
                billing_email=billing_email,
                status='placed'
            )

            # Create order items
            for item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product=item.variant.product,
                    variant=item.variant,
                    quantity=item.quantity,
                    price=item.variant.product.price,
                    size=item.variant.size
                )

            # Clear cart
            cart_items.delete()

            return Response({
                "message": "Cash on Delivery order placed successfully!",
                "order_id": order.order_id,
                "total_amount": str(final_total),
                "discount_applied": str(discount_amount)
            }, status=status.HTTP_201_CREATED)

        except Cart.DoesNotExist:
            return Response(
                {"error": "Cart not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": "Failed to create COD order", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        


@api_view(['GET'])
@authentication_classes([]) # Disables default authentication for this view
@permission_classes([AllowAny]) # Explicitly allows any user (authenticated or not)
def home_page_data(request):
    """
    API endpoint to get data for the home page.
    Returns categories, new arrival products, and potentially other featured items.
    """
    try:
        # --- Fetch Categories ---
        categories = Category.objects.all()
        categories_serializer = CategorySerializer(categories, many=True)

        # --- Fetch New Arrival Products ---
        # Filter products marked as new drops and order by creation date (or another relevant date)
        # Adjust the number of items fetched as needed (e.g., 10)
        new_arrivals = Product.objects.filter(is_new_drop=True).order_by('-id')[:10] # Assuming 'id' implies creation order, or use 'created_at' if available
        new_arrivals_serializer = ProductSerializer(
            new_arrivals, 
            many=True, 
            context={'request': request} # Pass request context for is_wishlisted field
        )

        # --- Example: Fetch Featured/Popular Products ---
        # You might want to filter based on sales, ratings, or just a random selection later.
        # For now, let's get some other products, maybe just the next set after new arrivals?
        # Or, if you have a specific 'featured' flag on Product, use that.
        # featured_products = Product.objects.filter(featured=True).order_by('-some_popularity_metric')[:8]
        # Alternatively, get products not in new arrivals:
        # featured_product_ids = Product.objects.exclude(id__in=new_arrivals).values_list('id', flat=True)[:10]
        # featured_products = Product.objects.filter(id__in=featured_product_ids)
        # featured_products_serializer = ProductSerializer(
        #     featured_products,
        #     many=True,
        #     context={'request': request}
        # )

        # --- Prepare Response Data ---
        data = {
            "status": "success",
            "message": "Home page data retrieved successfully",
            "data": {
                "categories": categories_serializer.data,
                "new_arrivals": new_arrivals_serializer.data,
                # "featured_products": featured_products_serializer.data, # Add if implemented
            }
        }
        return Response(data, status=status.HTTP_200_OK)

    except Exception as e:
        # It's good practice to log errors (e.g., import logging; logger = logging.getLogger(__name__); logger.error(e))
        print(f"Error in home_page_data: {e}") # Basic print for now, replace with logging
        data = {
            "status": "error",
            "message": f"An error occurred while fetching home page data: {str(e)}"
        }
        return Response(data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated]) # Require user to be logged in
def initiate_checkout(request):
    """
    API endpoint to initiate the checkout process.
    Gets items from the user's cart, receives shipping details, payment method, and an optional coupon code.
    Creates an Order object.
    """
    user = request.user
    coupon_code = request.data.get('coupon_code', '').strip() # Get coupon code from request

    # Get the user's cart and items
    try:
        cart = Cart.objects.get(user=user)
        cart_items = CartItem.objects.filter(cart=cart).select_related('variant__product')
        if not cart_items.exists():
            return Response({
                "status": "error",
                "message": "Your cart is empty. Cannot proceed to checkout."
            }, status=status.HTTP_400_BAD_REQUEST)
    except Cart.DoesNotExist:
        return Response({
            "status": "error",
            "message": "Your cart does not exist. Cannot proceed to checkout."
        }, status=status.HTTP_400_BAD_REQUEST)

    # Calculate initial total
    initial_total = sum(item.variant.product.price * item.quantity for item in cart_items)

    # Handle Coupon (if provided)
    applied_coupon = None
    discount_amount = 0
    from django.core.exceptions import ValidationError as DjangoValidationError  # <-- Add this import
    if coupon_code:
        try:
            coupon = Coupon.objects.get(code__iexact=coupon_code)
            if not coupon.is_valid():
                return Response({
                    "status": "error",
                    "message": "Coupon is not valid (check dates, status, or usage limit)."
                }, status=status.HTTP_400_BAD_REQUEST)

            if initial_total < float(coupon.minimum_order_amount):
                return Response({
                    "status": "error",
                    "message": f"Order total is less than the minimum required amount of ₹{coupon.minimum_order_amount} for this coupon."
                }, status=status.HTTP_400_BAD_REQUEST)

            # Optional: Check per-user usage limit
            # user_usage_count = Order.objects.filter(user=user, applied_coupon=coupon).count()
            # if coupon.per_user_limit and user_usage_count >= coupon.per_user_limit:
            #     return Response({
            #         "status": "error",
            #         "message": "You have reached the usage limit for this coupon."
            #     }, status=status.HTTP_400_BAD_REQUEST)

            discount_amount = coupon.calculate_discount(initial_total)
            applied_coupon = coupon # Set the coupon object for later use

        except Coupon.DoesNotExist:
            return Response({
                "status": "error",
                "message": "Invalid coupon code."
            }, status=status.HTTP_400_BAD_REQUEST)
        except DjangoValidationError as e:
            # Handle validation errors from coupon.clean()
            return Response({
                "status": "error",
                "message": f"Invalid coupon configuration: {e}"
            }, status=status.HTTP_400_BAD_REQUEST)

    # Use a new serializer specifically for the checkout request body
    serializer = CheckoutSerializer(data=request.data, context={'request': request, 'cart_items': cart_items, 'user': user})
    if serializer.is_valid():
        try:
            with transaction.atomic(): # Ensure all changes happen together
                order = serializer.save()

                # Apply coupon details to the order *after* it's created
                if applied_coupon:
                    order.applied_coupon = applied_coupon
                    order.discount_amount = discount_amount
                    order.total_amount = initial_total - discount_amount # Update total with discount
                    order.save() # Save the updated order

                    # Increment usage count (globally)
                    applied_coupon.used_count += 1
                    applied_coupon.save(update_fields=['used_count']) # Only update the count field

                # Clear the user's cart after successful order creation
                cart.items.all().delete() # Or cart.delete() if you want to remove the cart object itself, but usually clearing items is sufficient

                # Return the created order details
                response_data = {
                    "status": "success",
                    "message": "Order created successfully.",
                    "data": {
                        "order_id": order.order_id,
                        "order_details": OrderSerializer(order).data # Return full order data using your existing OrderSerializer
                    }
                }
                return Response(response_data, status=status.HTTP_201_CREATED)
        except Exception as e:
            # Log the error
            print(f"Error creating order: {e}")
            response_data = {
                "status": "error",
                "message": f"An error occurred while creating the order: {str(e)}"
            }
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    else:
        # Return validation errors
        response_data = {
            "status": "error",
            "message": "Invalid data provided.",
            "errors": serializer.errors
        }
        return Response(response_data, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny]) # Allow checking without login initially, but logic can require user later
def validate_coupon(request):
    """
    API endpoint to validate a coupon code against a given total amount.
    Expects:
    {
      "code": "COUPON_CODE",
      "total_amount": 1500.00
    }
    Returns:
    {
      "is_valid": true/false,
      "message": "Success or error message",
      "discount_amount": 150.00 (if valid)
    }
    """
    code = request.data.get('code')
    total_amount_str = request.data.get('total_amount')

    if not code or total_amount_str is None:
        return Response(
            {"error": "Coupon code and total amount are required."},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        total_amount_float = float(total_amount_str) # Original float value for comparison
    except (TypeError, ValueError):
        return Response(
            {"error": "Total amount must be a valid number."},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        coupon = Coupon.objects.get(code__iexact=code) # Case-insensitive match
    except Coupon.DoesNotExist:
        return Response(
            {"is_valid": False, "message": "Invalid coupon code."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Check validity
    if not coupon.is_valid():
        return Response(
            {"is_valid": False, "message": "Coupon is not valid (check dates, status, or usage limit)."},
            status=status.HTTP_400_BAD_REQUEST
        )

    if total_amount_float < float(coupon.minimum_order_amount):
        return Response(
            {"is_valid": False, "message": f"Order total is less than the minimum required amount of ₹{coupon.minimum_order_amount}."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Convert total_amount to Decimal for safe calculation with the coupon model
    total_amount_decimal = Decimal(str(total_amount_float))

    # Calculate discount using the FIXED calculate_discount method in models.py (returns Decimal)
    discount_amount_decimal = coupon.calculate_discount(total_amount_decimal)

    # Calculate final total (Decimal)
    final_total_decimal = total_amount_decimal - discount_amount_decimal

    return Response(
        {
            "is_valid": True,
            "message": "Coupon is valid.",
            "discount_amount": float(discount_amount_decimal), # Convert back to float for JSON response
            "final_total": float(final_total_decimal) # Convert back to float for JSON response
        },
        status=status.HTTP_200_OK
    )


@api_view(['POST'])
@permission_classes([AllowAny])
def calculate_shipping_api(request):
    """
    Calculate shipping cost based on location and total weight.
    Request: { "location": "Chennai", "total_weight_kg": 3.5 }
    Response: { "shipping_cost": 15.00 }
    """
    location = request.data.get('location', '').strip()
    weight_str = request.data.get('total_weight_kg')

    if weight_str is None:
        return Response(
            {"error": "total_weight_kg is required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        weight = float(weight_str)
        if weight < 0:
            raise ValueError("Weight cannot be negative")
    except (TypeError, ValueError, InvalidOperation):
        return Response(
            {"error": "total_weight_kg must be a valid non-negative number"},
            status=status.HTTP_400_BAD_REQUEST
        )

    shipping_cost = calculate_shipping_cost(location, weight)
    return Response({
        "shipping_cost": float(shipping_cost)
    }, status=status.HTTP_200_OK)