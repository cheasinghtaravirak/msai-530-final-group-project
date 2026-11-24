from django.urls import path

from . import views

urlpatterns = [
    path("auth/login", views.LoginView.as_view()),
    path("auth/me", views.MeView.as_view()),
    path("branches", views.BranchListView.as_view()),
    path("branches/<str:branch_id>", views.BranchDetailView.as_view()),
    path("branches/<str:branch_id>/close", views.BranchCloseView.as_view()),
    path("users", views.UserListView.as_view()),
    path("users/<uuid:user_id>", views.UserDetailView.as_view()),
    path("users/<uuid:user_id>/roles", views.UserRolesView.as_view()),
    path("users/<uuid:user_id>/roles/<uuid:grant_id>", views.UserRoleDetailView.as_view()),
]
