from django.contrib.auth.models import User
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import CheckIn, MemberShip
from core.serializers import CheckInSerializer, MemberShipSerializer
from .models import UserProfile
from .serializers import (
    MemberUserProfileSerializer,
    UserProfileSerializer,
    UserSerializer,
)
from .permissions import MemberProfileAccess, StaffOnly


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        user_profile = getattr(user, 'profile', None)
        memberships = MemberShip.objects.filter(user=user)
        check_in = CheckIn.objects.filter(user=user)

        return Response({
            "user": UserSerializer(user).data,
            "user_profile": (
                UserProfileSerializer(user_profile).data if user_profile else None
            ),
            "memberships": MemberShipSerializer(memberships, many=True).data,
            "check_in": CheckInSerializer(check_in, many=True).data,
        })


class MembersListView(generics.ListAPIView):
    serializer_class = MemberUserProfileSerializer
    permission_classes = [StaffOnly]
    queryset = UserProfile.objects.filter(role='member')


class MembersDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [MemberProfileAccess]
    queryset = UserProfile.objects.filter(role='member')


class StaffListView(generics.ListAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [StaffOnly]
    queryset = UserProfile.objects.all().exclude(role='member')


class StaffDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [StaffOnly]
    queryset = UserProfile.objects.all().exclude(role='member')
