from django.urls import path

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.home, name='home'),
    path('upload/', views.upload, name='upload'),
    path('documents/<int:pk>/delete/', views.delete_document, name='delete_document'),
    path('read/<int:pk>/', views.reader, name='reader'),
    path('read/<int:pk>/progress/', views.save_progress, name='save_progress'),
    path('read/<int:pk>/settings/', views.reader_settings, name='reader_settings'),
]
