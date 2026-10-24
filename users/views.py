from rest_framework import generics, permissions
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import CheckIn, MemberShip
from core.serializers import CheckInSerializer, MemberShipSerializer
from .models import UserProfile
from .serializers import (
    EmailLoginSerializer,
    EmailRegistrationSerializer,
    MemberUserProfileSerializer,
    UserProfileCompletionSerializer,
    UserProfileSerializer,
    UserSerializer,
)
from .permissions import MemberProfileAccess, StaffOnly


def token_pair_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


class EmailRegistrationView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = EmailRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(token_pair_for_user(user), status=201)


class EmailLoginView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = EmailLoginSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        return Response(token_pair_for_user(serializer.validated_data['user']))


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


class MeProfileCompletionView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        profile = UserProfile.objects.filter(user=request.user).first()
        serializer = UserProfileCompletionSerializer(
            profile,
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data)


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
