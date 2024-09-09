from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    path('', views.upload_view, name='upload'),
    path('results/', views.results_view, name='results'),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
