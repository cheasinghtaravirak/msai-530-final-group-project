from django.urls import path

from . import views

urlpatterns = [
    path("dims/branches", views.DimBranchListView.as_view()),
    path("reports/sales", views.SalesReportView.as_view()),
]
