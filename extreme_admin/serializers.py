from rest_framework import serializers
from .models import Admin
# from django.contrib.auth import get_user_model

class AdminLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get('email')
        password = data.get('password')

        try:
            admin = Admin.objects.get(email=email)
        except Admin.DoesNotExist:
            raise serializers.ValidationError("Invalid email or password")

        if not admin.check_password(password):
            raise serializers.ValidationError("Invalid email or password")

        data['admin'] = admin
        return data
    
