from django.urls import path
from . import views

urlpatterns = [
    path('', views.beneficiary_list_create, name='beneficiary-list-create'),
    path('<str:beneficiary_id>/', views.beneficiary_detail, name='beneficiary-detail'),
]
