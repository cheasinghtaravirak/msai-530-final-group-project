from django.urls import path

from . import views

urlpatterns = [
    path("orders", views.OrdersView.as_view()),
    path("orders/<uuid:order_id>", views.OrderDetailView.as_view()),
    path("orders/<uuid:order_id>/refund", views.RefundView.as_view()),
    path("internal/sales-summary", views.SalesSummaryView.as_view()),
]
