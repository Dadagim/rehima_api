from datetime import timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import *
from .models import *
from users.permissions import StaffOnly, is_staff_user
from users.serializers import UserProfileSerializer, UserSerializer



class MemberShipPlansListCreateView(generics.ListCreateAPIView):
    queryset = MemberShipPlans.objects.all()
    serializer_class = MemberShipPlanSerializer


class MemberShipPlansDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = MemberShipPlans.objects.all()
    serializer_class = MemberShipPlanSerializer

class MemberShipListCreateView(generics.ListCreateAPIView):
    serializer_class = MemberShipSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if is_staff_user(user):
            return MemberShip.objects.select_related(
                'user',
                'user__profile',
                'membership_plan',
            )
        return MemberShip.objects.filter(user=user).select_related(
            'user',
            'user__profile',
            'membership_plan',
        )

    def create(self, request, *args, **kwargs):
        if not is_staff_user(request.user):
            return Response(
                {'detail': 'Only staff can create memberships.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().create(request, *args, **kwargs)

class MemberShipDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = MemberShip.objects.all()
    serializer_class = MemberShipSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if is_staff_user(user):
            return MemberShip.objects.select_related(
                'user',
                'user__profile',
                'membership_plan',
            )
        return MemberShip.objects.filter(user=user).select_related(
            'user',
            'user__profile',
            'membership_plan',
        )

    def update(self, request, *args, **kwargs):
        if not is_staff_user(request.user):
            return Response(
                {'detail': 'Only staff can update memberships.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if not is_staff_user(request.user):
            return Response(
                {'detail': 'Only staff can update memberships.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not is_staff_user(request.user):
            return Response(
                {'detail': 'Only staff can delete memberships.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)

class CheckInListCreateView(APIView):
    permission_classes = [StaffOnly]

    def get(self, request):
        qs = CheckIn.objects.all()
        serializer = CheckInSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        qr_token = request.data.get('qr_token')
        if not qr_token:
            return Response(
                {'detail': 'A QR code is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            membership = MemberShip.objects.select_related(
                'user',
                'user__profile',
                'membership_plan',
            ).filter(qr_token=qr_token).first()
        except (ValidationError, ValueError, TypeError):
            membership = None

        if membership is None:
            return Response(
                {'detail': 'This QR code was not recognized.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        today = timezone.localdate()
        if membership.end_date and membership.end_date < today:
            CheckIn.objects.create(
                user=membership.user,
                membership=membership,
                is_successful=False,
            )
            return Response({
                'detail': f'Membership expired on {membership.end_date}.',
            }, status=status.HTTP_400_BAD_REQUEST)

        if membership.start_date > today:
            CheckIn.objects.create(
                user=membership.user,
                membership=membership,
                is_successful=False,
            )
            return Response(
                {'detail': f'Membership starts on {membership.start_date}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not membership.is_active:
            CheckIn.objects.create(
                user=membership.user,
                membership=membership,
                is_successful=False,
            )
            return Response(
                {'detail': 'Membership is not active.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        member = membership.user
        today_yesterday = today - timedelta(days=1)
        if member.profile.last_check_in_date == today_yesterday:
            member.profile.current_streak += 1
        else:
            member.profile.current_streak = 0

        CoinTransaction.objects.create(
            user=member,
            transaction_type='CHECK_IN',
            amount=10,
            description='Daily Check-In Reward',
        )
        member.profile.coins_balance += 10
        member.profile.last_check_in_date = today
        member.profile.save()

        check_in = CheckIn.objects.create(
            user=member,
            membership=membership,
            is_successful=True,
        )

        return Response({
            'detail': f'Check-in successful. Welcome back, {member.profile.full_name}!',
            'user': UserSerializer(member).data,
            'user_profile': UserProfileSerializer(member.profile).data,
            'membership': MemberShipSerializer(membership).data,
            'check_in': CheckInSerializer(check_in).data,
            'days_left': (membership.end_date - today).days,
        })


class CheckInDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = CheckIn.objects.all()
    serializer_class = CheckInSerializer
    permission_classes = [StaffOnly]
