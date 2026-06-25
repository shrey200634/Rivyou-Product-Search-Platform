from django.contrib import admin

from .models import Product, Tag


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'product_name', 'category', 'created_at')
    list_filter = ('category',)
    search_fields = ('product_name', 'product_description')
    filter_horizontal = ('tags',)
