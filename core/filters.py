# filters.py
import django_filters
from django.db.models import Q
from .models import Product, ProductVariant

class ProductFilter(django_filters.FilterSet):
    # Multi-value filters
    color = django_filters.CharFilter(method='filter_by_colors')
    size = django_filters.CharFilter(method='filter_by_sizes')
    material = django_filters.CharFilter(method='filter_by_materials')
    
    # Single-value filters
    category = django_filters.CharFilter(field_name='category__slug', lookup_expr='exact')
    price = django_filters.CharFilter(method='filter_by_price_range')

    class Meta:
        model = Product
        fields = []

    def filter_by_colors(self, queryset, name, value):
        if not value:
            return queryset
        colors = self.request.GET.getlist('color')  # handles ?color=Black&color=White
        if colors:
            q = Q()
            for color in colors:
                q |= Q(variants__color__iexact=color.strip())
            queryset = queryset.filter(q).distinct()
        return queryset

    def filter_by_sizes(self, queryset, name, value):
        if not value:
            return queryset
        sizes = self.request.GET.getlist('size')
        if sizes:
            q = Q()
            for size in sizes:
                q |= Q(variants__size=size.strip())
            queryset = queryset.filter(q).distinct()
        return queryset

    def filter_by_materials(self, queryset, name, value):
        if not value:
            return queryset
        materials = self.request.GET.getlist('material')
        if materials:
            q = Q()
            for mat in materials:
                q |= Q(materials__contains=[mat.strip()])
            queryset = queryset.filter(q)
        return queryset

    def filter_by_price_range(self, queryset, name, value):
        if value == 'under_500':
            return queryset.filter(price__lt=500)
        elif value == 'under_1000':
            return queryset.filter(price__lt=1000)
        elif value == 'under_2000':
            return queryset.filter(price__lt=2000)
        return queryset