from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import LoginForm

app_name = 'tracker'

urlpatterns = [
    path('', views.home, name='home'),
    path('companies/', views.company_list, name='company_list'),
    path('companies/create/', views.company_create, name='company_create'),
    path('companies/<int:pk>/', views.company_detail, name='company_detail'),
    path('companies/<int:pk>/edit/', views.company_edit, name='company_edit'),
    path(
        'companies/<int:company_id>/products/create/',
        views.product_create,
        name='product_create',
    ),
    path('products/<int:pk>/', views.product_detail, name='product_detail'),
    path('products/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('teams/', views.team_list, name='team_list'),
    path(
        'products/<int:product_id>/teams/create/',
        views.team_create,
        name='team_create',
    ),
    path('teams/<int:pk>/', views.team_detail, name='team_detail'),
    path('teams/<int:pk>/edit/', views.team_edit, name='team_edit'),
    path(
        'teams/<int:team_id>/members/add/',
        views.team_member_add,
        name='team_member_add',
    ),
    path(
        'teams/<int:team_id>/members/<int:membership_id>/delete/',
        views.team_member_delete,
        name='team_member_delete',
    ),
    path(
        'teams/<int:team_id>/tasks/create/',
        views.task_create,
        name='task_create',
    ),
    path('tasks/<int:pk>/', views.task_detail, name='task_detail'),
    path('tasks/<int:pk>/edit/', views.task_edit, name='task_edit'),
    path('register/', views.register, name='register'),
    path(
        'login/',
        auth_views.LoginView.as_view(
            template_name='tracker/registration/login.html',
            authentication_form=LoginForm,
            redirect_authenticated_user=True,
        ),
        name='login',
    ),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]
