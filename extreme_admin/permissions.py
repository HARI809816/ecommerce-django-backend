from rest_framework.permissions import BasePermission

class IsAdminAuthenticated(BasePermission):
    def has_permission(self, request, view):
        return hasattr(request.user, 'email') and hasattr(request.user, 'role')

class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return (
            hasattr(request.user, 'role') and 
            request.user.role == 'super_admin'
        )