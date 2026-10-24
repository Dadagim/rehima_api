from django.db import models
import uuid
from django.contrib.auth.models import User

ROLE_CHOICES = (
    ('member', 'Member'),
    ('coach', 'coach'),
    ('casher', 'casher'),
    ('admin', 'Admin'),
)


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    full_name = models.CharField(max_length=100, blank=True, default='')
    phone_number = models.CharField(max_length=20, blank=True, default='')
    attendance_plan_per_week = models.CharField(max_length=20, blank=True, default='')

    coins_balance = models.PositiveIntegerField(default=0)
    current_streak = models.PositiveIntegerField(default=0)
    last_check_in_date = models.DateField(blank=True, null=True)

    # Referral System
    referral_code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    referred_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name='referrals')

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')
    profile = models.ImageField(upload_to='profile_pics', blank=True)


    def __str__(self):
        return f'{self.role} - {self.user.username} -  Profile'
