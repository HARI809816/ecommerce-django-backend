# extreme_admin/authentication.py
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed
from .models import Admin

class AdminJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        try:
            user_id = validated_token['user_id']
            
            return Admin.objects.get(id=user_id)
        except Admin.DoesNotExist:
            
            raise InvalidToken("Admin not found")
        except Exception as e:
            
            raise InvalidToken("Invalid token structure")