from django.contrib import admin
from django.urls import path, include
from carbon_calculator.views import frontend_view

urlpatterns = [
    path('', frontend_view, name='frontend'),
    path('admin/', admin.site.urls),
    path('api/', include('carbon_calculator.urls')),
] 