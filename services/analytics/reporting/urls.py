from django.urls import path

from . import views

urlpatterns = [
    path("dims/branches", views.DimBranchListView.as_view()),
]
