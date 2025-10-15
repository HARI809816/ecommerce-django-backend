from django.urls import path, include
from rest_framework.routers import DefaultRouter
#from .views import ProductViewSet, SignupView, VerifyOTPView, LoginView, OrderTrackingView, FAQViewSet, OrderViewSet, VerifyLoginOTPView,CartViewSet, ChangeContactView
from .views import *

router = DefaultRouter()
router.register(r'products', ProductViewSet)
router.register(r'orders', OrderViewSet)
#router.register(r'reviews', ReviewViewSet)
router.register(r'faqs', FAQViewSet)
router.register(r'cart', CartViewSet, basename='cart')
router.register(r'wishlist', WishlistViewSet, basename='wishlist')


urlpatterns = [
    path('', include(router.urls)),
    path('signup/', SignupView.as_view()),
    path('verify-otp/', VerifyOTPView.as_view()),
    path('login/', LoginView.as_view()),
   # path('verify-login-otp/', VerifyLoginOTPView.as_view(), name="verify-login-otp"),
    path('track-order/', OrderTrackingView.as_view()),
    path("change-contact/", ChangeContactView.as_view(), name="change-contact"),
    path("complete-profile/", CompleteProfileView.as_view(), name="complete-profile"),
    path("resend-otp/", ResendOTPView.as_view(), name="resend-otp"),
    path('list/toggle/', ToggleWishlistView.as_view(), name='toggle-wishlist'),
    path('list/check/', CheckWishlistView.as_view(), name='check-wishlist'),
    path('user-profile/', user_profile, name='user-profile'),
    path('contact-us/', contact_us, name='contact-us'),
    path('place-order/', place_order, name='place-order'),
    path('create-order/', CreateOrderView.as_view(), name='create_order'),
    path('verify-payment/', VerifyPaymentView.as_view(), name='verify_payment'),
    path('create-cod-order/', CreateCODOrderView.as_view(), name='create_cod_order'),
    path('home/', home_page_data, name='home-page-data'),
    path('checkout/', initiate_checkout, name='initiate-checkout'),
    path('validate-coupon/',validate_coupon, name='validate-coupon'),
    path('calculate-shipping/', calculate_shipping_api, name='calculate-shipping'),

   # path('cart/', CartView.as_view()),
    # Add wishlist similarly
]