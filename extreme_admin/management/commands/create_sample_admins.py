from django.core.management.base import BaseCommand
from extreme_admin.models import Admin

class Command(BaseCommand):
    help = 'Creates a sample super admin and normal admin'

    def handle(self, *args, **options):
        # Super Admin
        if not Admin.objects.filter(email='super@admin.com').exists():
            sa = Admin(email='super@admin.com', role='super_admin')
            sa.set_password('super123')
            sa.save()
            self.stdout.write(
                self.style.SUCCESS('✅ Super Admin created: super@admin.com / super123')
            )

        # Normal Admin
        if not Admin.objects.filter(email='admin@admin.com').exists():
            na = Admin(email='admin@admin.com', role='admin')
            na.set_password('admin123')
            na.save()
            self.stdout.write(
                self.style.SUCCESS('✅ Normal Admin created: admin@admin.com / admin123')
            )