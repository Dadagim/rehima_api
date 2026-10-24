import tempfile
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from .models import UserProfile


class EmailAuthenticationTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_registration_creates_member_and_returns_jwt_pair(self):
        response = self.client.post(
            '/users/auth/register/',
            {
                'email': 'new-member@example.com',
                'password': 'Strong-password-123!',
                'password_confirm': 'Strong-password-123!',
                'full_name': 'New Member',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        user = User.objects.get(email='new-member@example.com')
        self.assertTrue(user.check_password('Strong-password-123!'))
        self.assertEqual(user.profile.full_name, 'New Member')
        self.assertEqual(user.profile.role, 'member')
        self.assertFalse(user.is_staff)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {response.data['access']}",
        )
        profile_response = self.client.get('/users/me/')
        self.assertEqual(profile_response.status_code, 200)
        self.assertEqual(profile_response.data['user']['email'], user.email)

    def test_login_authenticates_email_case_insensitively(self):
        User.objects.create_user(
            username='existing-member',
            email='Member@example.com',
            password='Strong-password-123!',
        )

        response = self.client.post(
            '/users/auth/login/',
            {
                'email': 'member@EXAMPLE.com',
                'password': 'Strong-password-123!',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_login_rejects_invalid_password_with_generic_error(self):
        User.objects.create_user(
            username='existing-member',
            email='member@example.com',
            password='Strong-password-123!',
        )

        response = self.client.post(
            '/users/auth/login/',
            {'email': 'member@example.com', 'password': 'wrong-password'},
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['detail'][0], 'Invalid email or password.')

    def test_login_rejects_ambiguous_duplicate_emails(self):
        for username in ('first-member', 'second-member'):
            User.objects.create_user(
                username=username,
                email='member@example.com',
                password='Strong-password-123!',
            )

        response = self.client.post(
            '/users/auth/login/',
            {
                'email': 'member@example.com',
                'password': 'Strong-password-123!',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['detail'][0], 'Invalid email or password.')

    def test_registration_rejects_duplicate_email_and_password_mismatch(self):
        User.objects.create_user(
            username='existing-member',
            email='member@example.com',
            password='Strong-password-123!',
        )
        duplicate = self.client.post(
            '/users/auth/register/',
            {
                'email': 'MEMBER@example.com',
                'password': 'Strong-password-123!',
                'password_confirm': 'Strong-password-123!',
            },
            format='json',
        )
        mismatch = self.client.post(
            '/users/auth/register/',
            {
                'email': 'new-member@example.com',
                'password': 'Strong-password-123!',
                'password_confirm': 'Different-password-123!',
            },
            format='json',
        )

        self.assertEqual(duplicate.status_code, 400)
        self.assertIn('email', duplicate.data)
        self.assertEqual(mismatch.status_code, 400)
        self.assertIn('password_confirm', mismatch.data)

    def test_refresh_rotates_token_and_logout_blacklists_refresh_token(self):
        user = User.objects.create_user(
            username='existing-member',
            email='member@example.com',
            password='Strong-password-123!',
        )
        refresh = RefreshToken.for_user(user)
        old_refresh = str(refresh)

        refreshed = self.client.post(
            '/users/auth/token/refresh/',
            {'refresh': old_refresh},
            format='json',
        )
        self.assertEqual(refreshed.status_code, 200, refreshed.data)
        self.assertIn('access', refreshed.data)
        self.assertIn('refresh', refreshed.data)
        self.assertNotEqual(refreshed.data['refresh'], old_refresh)

        logout = self.client.post(
            '/users/auth/logout/',
            {'refresh': refreshed.data['refresh']},
            format='json',
        )
        self.assertEqual(logout.status_code, 200, logout.data)

        reused_refresh = self.client.post(
            '/users/auth/token/refresh/',
            {'refresh': refreshed.data['refresh']},
            format='json',
        )
        self.assertEqual(reused_refresh.status_code, 401)


class MeViewTests(TestCase):
    def setUp(self):
        self.media_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.media_dir.cleanup)
        media_settings = override_settings(MEDIA_ROOT=self.media_dir.name)
        media_settings.enable()
        self.addCleanup(media_settings.disable)

    def image_upload(self):
        image = BytesIO()
        Image.new('RGB', (1, 1), color='white').save(image, format='PNG')
        return SimpleUploadedFile(
            'profile.png',
            image.getvalue(),
            content_type='image/png',
        )

    def test_superuser_without_profile_can_load_me_endpoint(self):
        user = User.objects.create_superuser(
            username='site-admin',
            email='admin@example.com',
            password='Strong-password-123!',
        )
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get('/users/me/')

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data['user_profile'])
        self.assertTrue(response.data['user']['is_superuser'])

    def test_profile_completion_creates_profile_for_user_without_one(self):
        user = User.objects.create_user(username='new-member', password='password')
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.post(
            '/users/me/profile/',
            {
                'full_name': 'New Member',
                'phone_number': '0400000000',
                'attendance_plan_per_week': '3',
                'profile': self.image_upload(),
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, 200, response.data)
        profile = user.profile
        self.assertEqual(profile.full_name, 'New Member')
        self.assertEqual(profile.phone_number, '0400000000')
        self.assertEqual(profile.attendance_plan_per_week, '3')
        self.assertTrue(profile.profile)
        self.assertEqual(profile.role, 'member')

    def test_profile_completion_requires_picture_for_incomplete_profile(self):
        user = User.objects.create_user(username='new-member', password='password')
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.post(
            '/users/me/profile/',
            {
                'full_name': 'New Member',
                'phone_number': '0400000000',
                'attendance_plan_per_week': '3',
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('profile', response.data)
        self.assertFalse(UserProfile.objects.filter(user=user).exists())

    def test_profile_completion_does_not_change_role_or_rewards(self):
        user = User.objects.create_user(username='coach', password='password')
        profile = UserProfile.objects.create(
            user=user,
            role='coach',
            coins_balance=25,
        )
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.post(
            '/users/me/profile/',
            {
                'full_name': 'Coach User',
                'phone_number': '0400000000',
                'attendance_plan_per_week': '4',
                'profile': self.image_upload(),
                'role': 'admin',
                'coins_balance': '9999',
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, 200, response.data)
        profile.refresh_from_db()
        self.assertEqual(profile.role, 'coach')
        self.assertEqual(profile.coins_balance, 25)
