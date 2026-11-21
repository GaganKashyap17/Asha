from django.urls import path
from . import views

urlpatterns = [
    path("status/", views.ivr_status, name="ivr-status"),
    path("beneficiaries/", views.ivr_beneficiaries, name="ivr-beneficiaries"),
    path("initiate/", views.ivr_initiate, name="ivr-initiate"),
    path("history/", views.ivr_history, name="ivr-history"),
]
