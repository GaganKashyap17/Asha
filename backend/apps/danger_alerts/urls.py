from django.urls import path
from . import views

urlpatterns = [
    path('', views.alert_list_create, name='alert-list-create'),
    path('<str:alert_id>/', views.alert_update, name='alert-update'),
]
