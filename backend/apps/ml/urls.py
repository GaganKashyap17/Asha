from django.urls import path
from . import views

urlpatterns = [
    path('predict/', views.predict_risk_view, name='ml-predict'),
    path('models/', views.models_metadata_view, name='ml-models'),
]
