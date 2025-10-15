# 🛍️ Extreme Culture – Django E-Commerce Backend

This repository contains the **backend** for **Extreme Culture**, a modern e-commerce platform built with **Django REST Framework (DRF)**. It provides a full-featured, secure, and scalable API for customer and admin operations.

> ✅ **Frontend**: Separate React app (not included)  
> 🔌 **Backend-only**: RESTful APIs for authentication, cart, checkout, orders, admin, and more  
> 💳 **Payments**: Razorpay (Online + COD)  
> 📱 **Auth**: Email or Phone + OTP (Twilio & Email)

---

## ✨ Core Features

### 🔐 **Authentication & User Management**
- Signup/Login via **email OR phone** (mutually exclusive)
- **6-digit OTP** verification (5-minute expiry)
- **Resend OTP** with 30s cooldown
- **Complete profile** (first/last name)
- **Update contact info** (email/phone) with re-verification

### 🛒 **Shopping Experience**
- **Product browsing** with advanced filters:
  - Size, color, material, price range, category
- **Search** by name/description
- **Wishlist**: Add, remove, toggle, bulk-check status
- **Cart management**: Add/update/remove with real-time stock validation

### 💰 **Checkout & Orders**
- **Cash on Delivery (COD)**
- **Online payments** via **Razorpay**
- **Payment verification** with HMAC signature validation
- **Order tracking** by `order_id` + `billing_email`
- **Coupon system**:
  - Percentage discount
  - Fixed amount off
  - **BOGO 50%** (Buy One Get One 50% off on selected products)

### 🚚 **Dynamic Shipping Calculator**
- **Free shipping** for **Chennai**
- **Zone-based base rates**:
  - Zone A (Surrounding Chennai): ₹10
  - Zone B (Rest of Tamil Nadu): ₹20
  - Zone C (Nearby states): ₹40
  - Zone D (Rest of India): ₹60
- **Weight-based surcharge**:
  - ≤2 kg: ₹0
  - 2–5 kg: ₹15
  - >5 kg: ₹30
- **API**: `POST /api/calculate-shipping/` for frontend cart preview

### 👥 **Admin Dashboard (JWT-Protected)**
- **Admin Login**: Email + password → JWT tokens
- **Role-based access**:
  - `admin`: View dashboard, orders, customers, products
  - `super_admin`: ✅ **Add products** (with variants/images), ✅ **Create coupons**

### 📞 **Customer Support**
- **Contact Us** form (stores messages in DB)
- **FAQs** (public API)
- **Home Page API**: Categories + New Arrivals

---

## 🛠️ Tech Stack

- **Python 3.10+**
- **Django 4.x** + **Django REST Framework**
- **Authentication**:
  - Customers: `TokenAuthentication`
  - Admins: **Custom JWT** (`rest_framework_simplejwt`)
- **Database**: PostgreSQL (recommended)
- **Libraries**:
  - `phonenumber-field` – phone validation
  - `django-filter` – advanced product filtering
  - `razorpay` – payment integration
  - `twilio` – SMS OTP
  - `python-decouple` – environment management

---

## 🗂️ Project Structure

extreme-culture/
├── core/                 # Customer APIs & models
│   ├── models.py         # CustomUser, Product, Order, Cart, Coupon, etc.
│   ├── views.py          # Auth, cart, checkout, shipping, etc.
│   ├── serializers.py    # DRF serializers
│   ├── filters.py        # ProductFilter
│   └── utils/
│       └── shipping.py   # Shipping calculator
├── admin/                # Admin-only APIs
│   ├── views.py          # Product, coupon, dashboard (Super Admin only)
│   ├── serializers.py
│   ├── authentication.py # AdminJWTAuthentication
│   └── permissions.py    # IsAdminAuthenticated, IsSuperAdmin
├── services/             # Business logic
│   └── coupon_service.py # BOGO logic
├── manage.py
└── requirements.txt
---

## 🚀 Setup

### 1. Clone & Install
bash
git clone https://github.com/HARI809816/extreme-culture-backend.git
cd extreme-culture-backend
python -m venv venv && source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt

Environment Variables (.env)

DEBUG=True
SECRET_KEY=your-django-secret-key
DATABASE_URL=postgres://user:password@localhost:5432/extreme_culture

# Email (for OTP)
EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=your@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# Twilio (SMS OTP)
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1234567890

# Razorpay
RAZORPAY_KEY_ID=...
RAZORPAY_KEY_SECRET=...


Run:
python manage.py makemigration
python manage.py migrate
python manage.py runserver

🧪 Testing with Postman
Customer flow: Use Token from /api/verify-otp/ in Authorization: Token <key>
Admin flow: Use access JWT from /admin/login/ in Authorization: Bearer <token>
