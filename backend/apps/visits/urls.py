from django.urls import path
from . import views

urlpatterns = [
    path('', views.visit_list_create, name='visit-list-create'),
    path('extract/', views.extract_visit, name='visit-extract'),
    path('<str:visit_id>/', views.visit_detail, name='visit-detail'),
    path('<str:visit_id>/correct/', views.visit_correct, name='visit-correct'),
    path('<str:visit_id>/confirm/', views.visit_confirm, name='visit-confirm'),
]
