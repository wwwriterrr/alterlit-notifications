# В api/urls.py (префикс /api/v1/):  path('notifications/', include('api.notifications.urls')),
from django.urls import path

from . import views

urlpatterns = [
    path('', views.Notifications.as_view(), name='notifications-list'),
    path('counts/', views.Counts.as_view(), name='notifications-counts'),
    path('read/', views.Read.as_view(), name='notifications-read'),
    path('delete/', views.Delete.as_view(), name='notifications-delete'),
    path('settings/', views.Settings.as_view(), name='notifications-settings'),
]
