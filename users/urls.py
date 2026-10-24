from django.urls import path
from rest_framework_simplejwt.views import TokenBlacklistView, TokenRefreshView
from .views import *

urlpatterns = [
    path('auth/register/', EmailRegistrationView.as_view()),
    path('auth/login/', EmailLoginView.as_view()),
    path('auth/token/refresh/', TokenRefreshView.as_view()),
    path('auth/logout/', TokenBlacklistView.as_view()),
    path('me/', MeView.as_view()),
    path('me/profile/', MeProfileCompletionView.as_view()),
    path('members/', MembersListView.as_view()),
    path('members/<int:pk>/', MembersDetailView.as_view()),
    path('staffs/', StaffListView.as_view()),
    path('staffs/<int:pk>/', StaffDetailView.as_view()),
]