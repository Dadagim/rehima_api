from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils.text import slugify

from .models import UserProfile


class EmailRegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    password_confirm = serializers.CharField(write_only=True, trim_whitespace=False)
    full_name = serializers.CharField(max_length=100, required=False, allow_blank=True)

    def validate_email(self, value):
        email = value.strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError(
                'An account with this email already exists. Please sign in.'
            )
        return email

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                'password_confirm': 'The passwords do not match.',
            })
        candidate = User(
            email=attrs['email'],
            username=attrs['email'],
        )
        validate_password(attrs['password'], user=candidate)
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        email = validated_data['email']
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError({
                'email': 'An account with this email already exists. Please sign in.',
            })

        base_username = slugify(email.split('@', 1)[0])[:140] or 'member'
        username = base_username
        suffix = 2
        while User.objects.filter(username=username).exists():
            username = f'{base_username[:145]}-{suffix}'
            suffix += 1

        user = User.objects.create_user(
            username=username,
            email=email,
            password=validated_data['password'],
        )
        UserProfile.objects.create(
            user=user,
            full_name=validated_data.get('full_name', '').strip(),
        )
        return user


class EmailLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        users = list(
            User.objects.filter(email__iexact=attrs['email'].strip()).order_by('pk')[:2]
        )
        if len(users) != 1:
            raise serializers.ValidationError(
                {'detail': 'Invalid email or password.'},
            )

        user = authenticate(
            request=self.context.get('request'),
            username=users[0].username,
            password=attrs['password'],
        )
        if user is None:
            raise serializers.ValidationError(
                {'detail': 'Invalid email or password.'},
            )
        attrs['user'] = user
        return attrs


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'is_staff', 'is_superuser']
        read_only_fields = fields


class MemberUserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = UserProfile
        fields = ['id', 'user', 'username', 'email', 'full_name', 'phone_number', 'role']


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = '__all__'


class UserProfileCompletionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = [
            'full_name',
            'phone_number',
            'attendance_plan_per_week',
            'profile',
        ]
        extra_kwargs = {
            'profile': {'required': False},
        }

    def validate(self, attrs):
        if not attrs.get('profile') and not (
            self.instance and self.instance.profile
        ):
            raise serializers.ValidationError({
                'profile': 'Please upload a profile picture.',
            })
        return attrs
