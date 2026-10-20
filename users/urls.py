from django.urls import path
from .views import *

urlpatterns = [
    path('me/', MeView.as_view()),
    path('members/', MembersListView.as_view()),
    path('members/<int:pk>/', MembersDetailView.as_view()),
    path('staffs/', StaffListView.as_view()),
    path('staffs/<int:pk>/', StaffDetailView.as_view()),
]