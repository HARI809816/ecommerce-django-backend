from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import AdminLoginSerializer
from .authentication import AdminJWTAuthentication
from .permissions import IsSuperAdmin, IsAdminAuthenticated
from core.models import CustomUser, Order, Product, Coupon
from decimal import Decimal
from django.db import models
from core.serializers import ProductSerializer, OrderSerializer, UserSerializer
from rest_framework.parsers import MultiPartParser, FormParser
from core.models import Category, ProductVariant, ProductImage
from django.db.models import Count,  CharField
from django.contrib.auth import get_user_model
from django.db.models.functions import Cast 
from django.db import IntegrityError





class AdminLoginView(APIView):
    permission_classes = []  # Allow unauthenticated access for login

    def post(self, request):
        serializer = AdminLoginSerializer(data=request.data)
        if serializer.is_valid():
            admin = serializer.validated_data['admin']
            refresh = RefreshToken()
            refresh['user_id'] = admin.id
            refresh['email'] = admin.email
            refresh['role'] = admin.role

            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'role': admin.role,
                'email': admin.email
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Example: Protected view (only super admin can access)
class AdminAddProductView(APIView):
    authentication_classes = [AdminJWTAuthentication]
    permission_classes = [IsAdminAuthenticated, IsSuperAdmin]
    parser_classes = [MultiPartParser, FormParser]  # For file uploads

    def post(self, request):
        try:
            # Extract data
            name = request.data.get('name')
            description = request.data.get('description', '')
            category_name = request.data.get('category')  # e.g., "New Arrival"
            materials = request.data.get('materials', '')  # Optional
            is_new_drop = request.data.get('is_new_drop', 'false').lower() == 'true'
            gender = request.data.get('gender', '')
            product_type = request.data.get('product_type', '')
            price = request.data.get('price', '0.00')
            sale_price = request.data.get('sale_price', '0.00')
            cost = request.data.get('cost', '0.00')
            status = request.data.get('status', 'Active')
            stock_status = request.data.get('stock_status', 'In Stock')
            size_specific_pricing = request.data.get('size_specific_pricing', 'false').lower() == 'true'

            # Validate required fields
            if not name or not category_name or not price:
                return Response(
                    {"error": "Name, Category, and Price are required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get or create category
            category, created = Category.objects.get_or_create(
                name=category_name,
                defaults={'slug': category_name.lower().replace(' ', '-')}
            )

            # Create product
            product = Product.objects.create(
                name=name,
                description=description,
                price=float(price),
                category=category,
                materials=[materials] if materials else [],
                is_new_drop=is_new_drop
            )

            # Handle sizes and variants
            sizes = ['XS', 'S', 'M', 'L', 'XL', 'XXL']
            for size in sizes:
                if request.data.get(size.lower()):  # Checkbox value
                    variant_price = float(price) if not size_specific_pricing else float(request.data.get(f'{size}_price', price))
                    ProductVariant.objects.create(
                        product=product,
                        color='Default',  # You can extend this later
                        size=size,
                        stock=0  # Set to 0 initially; admin can update later
                    )

            # Handle images
            files = request.FILES.getlist('images')  # Field name must be 'images'
            for file in files:
                ProductImage.objects.create(product=product, image=file)

            # Return success
            return Response({
                "message": "Product added successfully!",
                "product_id": product.id,
                "name": product.name,
                "category": category.name,
                "variants": list(product.variants.values('id', 'size', 'stock')),
                "images": list(product.images.values('id', 'image'))
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {"error": f"Failed to add product: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        

class AdminDashboardView(APIView):
    authentication_classes = [AdminJWTAuthentication]
    permission_classes = [IsAdminAuthenticated]

    def get(self, request):
        # Stats (available to all admins)
        total_customers = CustomUser.objects.count()
        total_orders = Order.objects.count()
        total_products = Product.objects.count()
        total_revenue = Order.objects.aggregate(
            total=models.Sum('total_amount')
        )['total'] or 0

        data = {
            "total_customers": total_customers,
            "total_orders": total_orders,
            "total_products": total_products,
            "total_revenue": float(total_revenue),
            "role": request.user.role,
        }

        # Super Admin sees more (e.g., recent orders)
        if request.user.role == 'super_admin':
            recent_orders = Order.objects.select_related('user').order_by('-created_at')[:5]
            data["recent_orders"] = [
                {
                    "order_id": order.order_id,
                    "customer": order.user.email or str(order.user.phone_number),
                    "amount": float(order.total_amount),
                    "status": order.status,
                    "date": order.created_at.isoformat()
                }
                for order in recent_orders
            ]

        return Response(data)
    
# Example: Product list view (any admin can access)
class AdminProductListView(APIView):
    authentication_classes = [AdminJWTAuthentication]
    permission_classes = [IsAdminAuthenticated]

    def get(self, request):
        products = Product.objects.prefetch_related('variants', 'images')
        serializer = ProductSerializer(products, many=True, context={'request': request})
        return Response(serializer.data)


class AdminOrderListView(APIView):
    authentication_classes = [AdminJWTAuthentication]
    permission_classes = [IsAdminAuthenticated]

    def get(self, request):
        orders = Order.objects.select_related('user').prefetch_related('items__product')
        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)

# class AdminCustomerListView(APIView):
#     authentication_classes = [AdminJWTAuthentication]
#     permission_classes = [IsAdminAuthenticated]

#     def get(self, request):
#         customers = CustomUser.objects.all()
#         serializer = UserSerializer(customers, many=True)
#         return Response(serializer.data)


CustomUser = get_user_model()

class AdminCustomerListView(APIView):
    authentication_classes = [AdminJWTAuthentication]
    permission_classes = [IsAdminAuthenticated]

    def get(self, request):
        customers = CustomUser.objects.annotate(
            total_orders=Count('order'),
            phone_str=Cast('phone_number', CharField()),  # Convert to string
            
        ).values(
            'id',
            'first_name',
            'last_name',
            'email',
            'address',
            'total_orders',
            'date_joined',
            'phone_str'  
        )
            # Manually format date_joined as date-only
        result = []
        for cust in customers:
            user = CustomUser.objects.get(id=cust['id'])
            result.append({
                **cust,
                'date_joined': user.date_joined.strftime('%Y-%m-%d')  # Format date
            })

        return Response(result)
    
class AdminCreateCouponView(APIView):
    authentication_classes = [AdminJWTAuthentication]
    permission_classes = [IsAdminAuthenticated, IsSuperAdmin]

    def post(self, request):
        try:
            code = request.data.get('code')
            discount_type = request.data.get('discount_type')
            discount_value = request.data.get('discount_value')
            minimum_order_amount = request.data.get('minimum_order_amount', 0)
            valid_from = request.data.get('valid_from')
            valid_to = request.data.get('valid_to')
            usage_limit = request.data.get('usage_limit', None)
            is_active = request.data.get('is_active', True)
            is_new_user_only = request.data.get('is_new_user_only', False)  # ✅ NEW FIELD
            product_ids = request.data.get('applicable_products', [])

            # Validate required fields
            if not all([code, discount_type]):
                return Response({"error": "Code and discount type are required."}, status=status.HTTP_400_BAD_REQUEST)

            # CHECK UNIQUENESS FIRST
            if Coupon.objects.filter(code=code).exists():
                return Response(
                    {"error": f"Coupon code '{code}' already exists."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate numeric values
            try:
                discount_value = Decimal(str(discount_value))
                minimum_order_amount = Decimal(str(minimum_order_amount))
                if usage_limit is not None:
                    usage_limit = int(usage_limit)
            except (ValueError, TypeError):
                return Response({"error": "Invalid numeric values."}, status=status.HTTP_400_BAD_REQUEST)

            # NOW create — safe because we checked uniqueness
            coupon = Coupon.objects.create(
                code=code,
                discount_type=discount_type,
                discount_value=discount_value,
                minimum_order_amount=minimum_order_amount,
                valid_from=valid_from,
                valid_to=valid_to,
                usage_limit=usage_limit,
                is_active=is_active,
                is_new_user_only=is_new_user_only  # ✅ SAVE NEW FIELD
            )

            # Handle BOGO products
            if discount_type == 'bogo_50':
                if not product_ids:
                    coupon.delete()
                    return Response(
                        {"error": "BOGO coupons require at least one applicable product."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                try:
                    products = Product.objects.filter(id__in=product_ids)
                    coupon.applicable_products.set(products)
                except Exception as e:
                    coupon.delete()
                    return Response({"error": f"Invalid product IDs: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

            return Response({
                "message": "Coupon created successfully",
                "coupon_id": coupon.id,
                "code": coupon.code,
                "discount_type": coupon.discount_type,
                "is_new_user_only": coupon.is_new_user_only  # ✅ INCLUDE IN RESPONSE
            }, status=status.HTTP_201_CREATED)

        except IntegrityError:
            return Response(
                {"error": f"Coupon code '{code}' already exists (concurrent request)."},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)