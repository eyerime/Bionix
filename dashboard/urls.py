from django.urls import path

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.home, name='home'),
    path('upload/', views.upload, name='upload'),
    path('documents/<int:pk>/delete/', views.delete_document, name='delete_document'),
]
