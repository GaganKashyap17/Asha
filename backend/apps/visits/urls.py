from django.urls import path
from . import views

urlpatterns = [
    # Existing endpoints — unchanged
    path('', views.visit_list_create, name='visit-list-create'),
    path('extract/', views.extract_visit, name='visit-extract'),

    # New revisit endpoints (must come before <visit_id>/ to avoid route conflicts)
    path('revisit/init/', views.revisit_init, name='revisit-init'),
    path('revisit/extract/', views.revisit_extract, name='revisit-extract'),
    path('revisit/extract-field/', views.revisit_extract_field, name='revisit-extract-field'),

    path('<str:visit_id>/', views.visit_detail, name='visit-detail'),
    path('<str:visit_id>/correct/', views.visit_correct, name='visit-correct'),
    path('<str:visit_id>/confirm/', views.visit_confirm, name='visit-confirm'),

    # Draft management endpoints
    path('draft/<str:draft_id>/', views.draft_detail, name='draft-detail'),
    path('draft/<str:draft_id>/add-field/', views.draft_add_field, name='draft-add-field'),
    path('draft/<str:draft_id>/confirm/', views.draft_confirm, name='draft-confirm'),
    path('draft/<str:draft_id>/discard/', views.draft_discard, name='draft-discard'),
]
