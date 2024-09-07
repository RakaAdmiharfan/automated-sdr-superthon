from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.upload_view, name='upload'),
    path('results/', views.results_view, name='results'),
]
