from django.urls import path

from . import views

urlpatterns = [
    path("pos/items", views.PosItemsView.as_view()),
]
