from django.urls import path

from . import views

urlpatterns = [
    path("jobs/runs", views.JobRunListView.as_view()),
    path("jobs/runs/<uuid:run_id>", views.JobRunDetailView.as_view()),
    path("jobs/<str:job>/run", views.RunJobView.as_view()),
]
