from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('health/', views.health_check, name='health'),
]
