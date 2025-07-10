from django.urls import path
from . import views

urlpatterns = [
    path('form-options/', views.get_form_options, name='form_options'),
    path('health/', views.health_check, name='health_check'),
    path('carbon-model/', views.carbon_model, name='carbon_model'),
    path('download-report/', views.download_report, name='download_report'),
]
