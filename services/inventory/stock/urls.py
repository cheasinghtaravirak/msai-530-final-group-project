from django.urls import path

from . import views

urlpatterns = [
    path("stock", views.StockView.as_view()),
    path("stock/<str:branch_id>/<str:sku>/movements", views.MovementsView.as_view()),
    path("adjustments", views.AdjustmentsView.as_view()),
]
