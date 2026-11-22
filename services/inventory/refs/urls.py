from django.urls import path

from . import views

urlpatterns = [
    path("refs/branches", views.BranchRefListView.as_view()),
]
