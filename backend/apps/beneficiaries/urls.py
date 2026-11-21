from django.urls import path
from . import views

urlpatterns = [
    path('', views.beneficiary_list_create, name='beneficiary-list-create'),
    path('register-voice/', views.beneficiary_register_voice, name='beneficiary-register-voice'),
    path('extract-field/', views.beneficiary_extract_field, name='beneficiary-extract-field'),
    path('check-duplicate/', views.beneficiary_check_duplicate, name='beneficiary-check-duplicate'),
    path('lookup/<str:beneficiary_id>/', views.beneficiary_lookup, name='beneficiary-lookup'),
    path('<str:beneficiary_id>/', views.beneficiary_detail, name='beneficiary-detail'),
]
