from django.urls import path

from . import views

urlpatterns = [
    path("categories", views.CategoryListView.as_view()),
    path("products", views.ProductListView.as_view()),
    path("products/<uuid:product_id>", views.ProductDetailView.as_view()),
    path("skus/<str:sku>", views.SkuDetailView.as_view()),
    path("prices/<str:sku>", views.PriceView.as_view()),
    path("suppliers", views.SupplierListView.as_view()),
    path("suppliers/<uuid:supplier_id>", views.SupplierDetailView.as_view()),
    path("suppliers/<uuid:supplier_id>/skus/<str:sku>", views.SupplierSkuView.as_view()),
]
