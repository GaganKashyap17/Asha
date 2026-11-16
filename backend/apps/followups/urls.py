from django.urls import path
from . import views

urlpatterns = [
    path('', views.followup_list, name='followup-list'),
    path('<str:followup_id>/', views.followup_update, name='followup-update'),
]
