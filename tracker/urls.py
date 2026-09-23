from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = 'tracker'

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path(
        'login/',
        auth_views.LoginView.as_view(
            template_name='tracker/registration/login.html',
            redirect_authenticated_user=True,
        ),
        name='login',
    ),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]
