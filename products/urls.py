from django.urls import path

from .views import (
    ProductByCategoryView,
    ProductCreateView,
    ProductDetailView,
    ProductSearchView,
)

urlpatterns = [
    path('search', ProductSearchView.as_view(), name='product-search'),
    path('category/<str:category>', ProductByCategoryView.as_view(), name='product-by-category'),
    path('<int:pk>', ProductDetailView.as_view(), name='product-detail'),
    path('', ProductCreateView.as_view(), name='product-create'),
]
