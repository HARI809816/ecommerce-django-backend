from django.urls import path
from .views import *

urlpatterns = [
    path('adminlogin/', AdminLoginView.as_view(), name='admin-login'),
    path('dashboard/', AdminDashboardView.as_view(), name='admin-dashboard'),
    path('products/', AdminProductListView.as_view(), name='admin-products'),
    path('products/add/', AdminAddProductView.as_view(), name='admin-add-product'),
    path('orders/', AdminOrderListView.as_view(), name='admin-orders'),
    path('customers/', AdminCustomerListView.as_view(), name='admin-customers'),
    path('coupons/create/', AdminCreateCouponView.as_view(), name='admin-create-coupon'),
]