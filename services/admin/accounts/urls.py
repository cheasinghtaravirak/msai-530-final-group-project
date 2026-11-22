from django.urls import path

from . import views

urlpatterns = [
    path("auth/login", views.LoginView.as_view()),
    path("auth/me", views.MeView.as_view()),
    path("branches", views.BranchListView.as_view()),
    path("branches/<str:branch_id>", views.BranchDetailView.as_view()),
]
