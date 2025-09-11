"""
URL configuration for DocAi project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include
from . import views
from django.conf import settings
from django.conf.urls.static import static
urlpatterns = [
    path('admin/', admin.site.urls),
    path('',views.home_view,name='home'),
    path('login/',views.login_view,name='login'),
    path('register/',views.register_view,name='register'),
     path("detection/", include("detection.urls")),path('check-username/', views.check_username_availability, name='check_username_availability'),
    path('check-email/', views.check_email_availability, name='check_email_availability'),
    path('logout',views.logout_view , name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('help/', views.help_view, name='help'),
    path('contact/', views.contact_view, name='contact'),
    path('password-reset/', views.password_reset_request_view, name='password_reset'), 
    

]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
