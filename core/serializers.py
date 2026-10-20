from rest_framework import serializers
from .models import *





class MemberShipPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = MemberShipPlans
        fields = '__all__'


class MemberShipSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    member_name = serializers.SerializerMethodField()
    membership_plan_name = serializers.CharField(
        source='membership_plan.name',
        read_only=True,
    )
    membership_plan_duration = serializers.IntegerField(
        source='membership_plan.duration',
        read_only=True,
    )
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = MemberShip
        fields = '__all__'
        read_only_fields = ['qr_token', 'qr_code_image', 'created_at']

    def get_member_name(self, membership):
        profile = getattr(membership.user, 'profile', None)
        return profile.full_name if profile else membership.user.username


class CheckInSerializer(serializers.ModelSerializer):
    class Meta:
        model = CheckIn
        fields = '__all__'

class CoinTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CoinTransaction
        fields = '__all__'
