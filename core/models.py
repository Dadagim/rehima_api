from datetime import timedelta

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid
import qrcode
from io import BytesIO
from django.core.files import File

class MemberShipPlans(models.Model):
    name = models.CharField(max_length=20)
    image = models.ImageField(upload_to='membership_plan_banner_images/')
    duration = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)


    def __str__(self):
        return f'{self.name} - {self.price} - {self.duration} '


class CoinTransaction(models.Model):
    TRANSACTION_TYPES = (
        ('CHECK_IN', 'Daily Check-In Reward'),
        ('STREAK_BONUS', 'Full Streak Bonus'),
        ('REFERRAL', 'Friend Referral Bonus'),
        ('REDEMPTION', 'Free Ticket Redemption'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='coin_transactions')
    amount = models.IntegerField()  # Can be positive (earned) or negative (spent)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}: {self.amount} coins ({self.transaction_type})"






class MemberShip(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='memberships')
    membership_plan = models.ForeignKey(MemberShipPlans, on_delete=models.CASCADE, related_name='memberships', default=None)
    start_date = models.DateField(default=timezone.localdate)
    end_date = models.DateField(blank=True, null=True)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)

    # Unique QR code per monthly plan (as discussed)
    qr_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    qr_code_image = models.ImageField(upload_to='membership_qrs/', blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.end_date:
            self.end_date = self.start_date + timedelta(
                days=self.membership_plan.duration
            )

        if not self.qr_code_image:
            qr_code = qrcode.QRCode(version=1, box_size=5, border=5)
            qr_code.add_data(str(self.qr_token))

            qr_code.make(fit=True)

            img = qr_code.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format="PNG")

            file_name = f'membership_qr_{self.qr_token}.png'

            self.qr_code_image.save(file_name, File(buffer), save=False)

        super().save(*args, **kwargs)



    @property
    def is_active(self):
        return bool(
            self.end_date
            and self.start_date <= timezone.localdate() <= self.end_date
        )



    def __str__(self):
        return f'{self.user.username} - {self.start_date} - {self.end_date} - {self.is_active}'

class CheckIn(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='check_in')
    membership = models.ForeignKey(MemberShip, on_delete=models.CASCADE, related_name='membership')
    is_successful = models.BooleanField(default=True)
    created_at = models.DateField(auto_now_add=True)


    def save(self, *args, **kwargs):
        if self.is_successful:
            self.is_successful = self.membership.is_active
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.user.username} - {self.membership.membership_plan.name} - {self.created_at}'
