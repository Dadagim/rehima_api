from django.urls import path
from .views import *

urlpatterns = [
    path('membership-plans/', MemberShipPlansListCreateView.as_view()),
    path('membership-plans/<int:pk>/', MemberShipPlansDetailView.as_view()),
    path('memberships/', MemberShipListCreateView.as_view()),
    path('memberships/<int:pk>/', MemberShipDetailView.as_view()),
    path('check-ins/', CheckInListCreateView.as_view()),
    path('check-ins/<int:pk>/', CheckInDetailView.as_view()),
]