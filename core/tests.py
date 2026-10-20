from datetime import datetime, timedelta, timezone as datetime_timezone
from decimal import Decimal
from io import BytesIO
import tempfile
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from core.models import CheckIn, CoinTransaction, MemberShip, MemberShipPlans
from users.models import UserProfile


class MembershipAccessTests(TestCase):
    def setUp(self):
        self.media_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.media_dir.cleanup)
        settings_override = override_settings(MEDIA_ROOT=self.media_dir.name)
        settings_override.enable()
        self.addCleanup(settings_override.disable)

        self.staff = self.create_user('staff', role='coach')
        self.member = self.create_user('member')
        self.other_member = self.create_user('other-member')
        self.plan = MemberShipPlans.objects.create(
            name='Monthly',
            image=self.image_upload('plan.png'),
            duration=30,
            price=Decimal('45.00'),
        )
        self.client = APIClient()
        self.url = '/api/memberships/'

    def image_upload(self, filename):
        buffer = BytesIO()
        Image.new('RGB', (1, 1), color='white').save(buffer, format='PNG')
        return SimpleUploadedFile(filename, buffer.getvalue(), content_type='image/png')

    def create_user(self, username, role='member'):
        user = User.objects.create_user(username=username, password='pass')
        UserProfile.objects.create(
            user=user,
            full_name=username.title(),
            phone_number='1234567890',
            role=role,
            profile=self.image_upload(f'{username}.png'),
        )
        return user

    def membership_data(self, member=None):
        return {
            'user': (member or self.member).pk,
            'membership_plan': self.plan.pk,
            'start_date': timezone.localdate().isoformat(),
            'amount_paid': '45.00',
        }

    def test_only_staff_can_create_memberships_and_qr_is_returned(self):
        self.client.force_authenticate(user=self.member)
        denied = self.client.post(self.url, self.membership_data(), format='json')
        self.assertEqual(denied.status_code, 403)

        self.client.force_authenticate(user=self.staff)
        response = self.client.post(self.url, self.membership_data(), format='json')

        self.assertEqual(response.status_code, 201, response.data)
        membership = MemberShip.objects.get(pk=response.data['id'])
        self.assertEqual(membership.user, self.member)
        self.assertEqual(
            membership.end_date,
            membership.start_date + timedelta(days=self.plan.duration),
        )
        self.assertTrue(membership.qr_code_image.name)
        self.assertTrue(response.data['qr_code_image'])

    @override_settings(TIME_ZONE='Australia/Sydney')
    def test_membership_starting_today_in_business_timezone_is_active(self):
        instant = datetime(
            2026,
            10,
            18,
            14,
            30,
            tzinfo=datetime_timezone.utc,
        )
        with timezone.override('Australia/Sydney'):
            start_date = timezone.localdate()
            self.client.force_authenticate(user=self.staff)
            with patch('django.utils.timezone.now', return_value=instant):
                response = self.client.post(
                    self.url,
                    {
                        **self.membership_data(),
                        'start_date': start_date.isoformat(),
                    },
                    format='json',
                )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data['is_active'])
        self.assertEqual(response.data['start_date'], '2026-10-19')

    def test_members_only_see_their_own_memberships(self):
        own = MemberShip.objects.create(
            user=self.member,
            membership_plan=self.plan,
            amount_paid=Decimal('45.00'),
        )
        other = MemberShip.objects.create(
            user=self.other_member,
            membership_plan=self.plan,
            amount_paid=Decimal('45.00'),
        )

        self.client.force_authenticate(user=self.member)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['id'] for item in response.data], [own.pk])
        self.assertNotIn(other.pk, [item['id'] for item in response.data])

    def test_staff_can_list_membership_candidates(self):
        self.client.force_authenticate(user=self.staff)

        response = self.client.get('/users/members/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {member['username'] for member in response.data},
            {'member', 'other-member'},
        )

    def test_member_cannot_promote_themselves_to_staff(self):
        self.client.force_authenticate(user=self.member)

        response = self.client.patch(
            f'/users/members/{self.member.profile.pk}/',
            {'role': 'admin'},
            format='json',
        )

        self.assertEqual(response.status_code, 403)
        self.member.profile.refresh_from_db()
        self.assertEqual(self.member.profile.role, 'member')

    def test_only_staff_can_scan_membership_qr_codes(self):
        membership = MemberShip.objects.create(
            user=self.member,
            membership_plan=self.plan,
            amount_paid=Decimal('45.00'),
        )

        self.client.force_authenticate(user=self.member)
        response = self.client.post(
            '/api/check-ins/',
            {'qr_token': str(membership.qr_token)},
            format='json',
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(CheckIn.objects.exists())

    def test_staff_scan_of_active_membership_returns_success(self):
        membership = MemberShip.objects.create(
            user=self.member,
            membership_plan=self.plan,
            amount_paid=Decimal('45.00'),
        )
        self.client.force_authenticate(user=self.staff)

        response = self.client.post(
            '/api/check-ins/',
            {'qr_token': str(membership.qr_token)},
            format='json',
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn('Check-in successful', response.data['detail'])
        self.assertEqual(response.data['user']['id'], self.member.pk)
        self.assertEqual(response.data['user']['username'], self.member.username)
        self.assertEqual(response.data['user_profile']['full_name'], self.member.profile.full_name)
        self.assertEqual(response.data['user_profile']['phone_number'], self.member.profile.phone_number)
        self.assertEqual(response.data['membership']['id'], membership.pk)
        self.assertEqual(response.data['membership']['membership_plan_name'], self.plan.name)
        self.assertTrue(response.data['check_in']['is_successful'])
        self.assertTrue(CheckIn.objects.get().is_successful)
        self.assertEqual(CoinTransaction.objects.filter(user=self.member).count(), 1)

    def test_admin_role_can_scan_membership_qr_codes(self):
        admin = self.create_user('admin', role='admin')
        membership = MemberShip.objects.create(
            user=self.member,
            membership_plan=self.plan,
            amount_paid=Decimal('45.00'),
        )
        self.client.force_authenticate(user=admin)

        response = self.client.post(
            '/api/check-ins/',
            {'qr_token': str(membership.qr_token)},
            format='json',
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(CheckIn.objects.get().is_successful)

    def test_staff_scan_of_expired_membership_returns_error_and_records_failed_checkin(self):
        today = timezone.localdate()
        membership = MemberShip.objects.create(
            user=self.member,
            membership_plan=self.plan,
            start_date=today - timedelta(days=31),
            end_date=today - timedelta(days=1),
            amount_paid=Decimal('45.00'),
        )
        self.client.force_authenticate(user=self.staff)

        response = self.client.post(
            '/api/check-ins/',
            {'qr_token': str(membership.qr_token)},
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('Membership expired', response.data['detail'])
        self.assertFalse(CheckIn.objects.get().is_successful)
        self.assertFalse(CoinTransaction.objects.exists())

    def test_staff_scan_rejects_missing_or_unrecognized_qr_code(self):
        self.client.force_authenticate(user=self.staff)

        missing = self.client.post('/api/check-ins/', {}, format='json')
        unrecognized = self.client.post(
            '/api/check-ins/',
            {'qr_token': 'not-a-uuid'},
            format='json',
        )

        self.assertEqual(missing.status_code, 400)
        self.assertEqual(unrecognized.status_code, 404)
