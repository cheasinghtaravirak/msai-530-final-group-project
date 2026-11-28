from django.urls import path

from . import views

urlpatterns = [
    path("receipts", views.ReceiptsView.as_view()),
]
