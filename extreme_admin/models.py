from django.db import models
from django.contrib.auth.hashers import make_password, check_password

class Admin(models.Model):
    ROLE_CHOICES = [
        ('super_admin', 'Super Admin'),
        ('admin', 'Normal Admin'),
    ]

    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='admin')
    created_at = models.DateTimeField(auto_now_add=True)

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    @property
    def is_authenticated(self):
        return True  # ✅ Fixes IsAuthenticated permission

    def __str__(self):
        return f"{self.email} ({self.role})"