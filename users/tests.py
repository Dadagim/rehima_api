from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIClient

from .authentication import ClerkAuthentication, verify_clerk_token
from .clerk import AccountLinkConflict, ClerkConfigurationError, sync_clerk_user
from .models import UserProfile


class ClerkUserProvisioningTests(TestCase):
    def setUp(self):
        self.identity = {
            'id': 'user_clerk_123',
            'username': 'new-member',
            'first_name': 'New',
            'last_name': 'Member',
            'primary_email_address_id': 'email_primary',
            'email_addresses': [
                {
                    'id': 'email_primary',
                    'email_address': 'member@example.com',
                    'verification': {'status': 'verified'},
                },
            ],
            'primary_phone_number_id': 'phone_primary',
            'phone_numbers': [
                {'id': 'phone_primary', 'phone_number': '+61123456789'},
            ],
        }

    @patch('users.clerk.fetch_clerk_user')
    def test_verified_email_links_existing_profile_and_preserves_role(self, fetch_user):
        existing = User.objects.create_user(
            username='existing-member',
            email='member@example.com',
            password='Strong-password-123!',
        )
        profile = UserProfile.objects.create(
            user=existing,
            full_name='Existing Member',
            phone_number='0400000000',
            role='coach',
        )
        fetch_user.return_value = self.identity

        linked = sync_clerk_user('user_clerk_123')

        profile.refresh_from_db()
        self.assertEqual(linked, existing)
        self.assertEqual(profile.clerk_id, 'user_clerk_123')
        self.assertEqual(profile.role, 'coach')
        self.assertEqual(profile.full_name, 'Existing Member')
        self.assertEqual(profile.phone_number, '0400000000')

    @patch('users.clerk.fetch_clerk_user')
    def test_new_clerk_user_gets_member_profile_without_local_password(self, fetch_user):
        fetch_user.return_value = self.identity

        user = sync_clerk_user('user_clerk_123')

        self.assertEqual(user.email, 'member@example.com')
        self.assertFalse(user.has_usable_password())
        self.assertEqual(user.profile.clerk_id, 'user_clerk_123')
        self.assertEqual(user.profile.role, 'member')
        self.assertEqual(user.profile.full_name, 'New Member')
        self.assertEqual(user.profile.phone_number, '+61123456789')
        self.assertFalse(user.profile.profile)

    @patch('users.clerk.fetch_clerk_user')
    def test_unverified_email_does_not_link_existing_account(self, fetch_user):
        existing = User.objects.create_user(
            username='existing-member',
            email='member@example.com',
            password='Strong-password-123!',
        )
        fetch_user.return_value = {
            **self.identity,
            'email_addresses': [
                {
                    'id': 'email_primary',
                    'email_address': 'member@example.com',
                    'verification': {'status': 'unverified'},
                },
            ],
        }

        user = sync_clerk_user('user_clerk_123')

        self.assertNotEqual(user, existing)
        self.assertEqual(user.email, '')
        self.assertFalse(UserProfile.objects.filter(user=existing, clerk_id__isnull=False).exists())

    @patch('users.clerk.fetch_clerk_user')
    def test_duplicate_existing_email_is_rejected(self, fetch_user):
        for username in ('first', 'second'):
            User.objects.create_user(
                username=username,
                email='member@example.com',
                password='Strong-password-123!',
            )
        fetch_user.return_value = self.identity

        with self.assertRaises(AccountLinkConflict):
            sync_clerk_user('user_clerk_123')

    @patch('users.authentication.sync_clerk_user')
    @patch('users.authentication.verify_clerk_token')
    def test_bearer_token_authenticates_linked_django_user(self, verify_token, sync_user):
        user = User.objects.create_user(username='member', password='password')
        verify_token.return_value = {'sub': 'user_clerk_123'}
        sync_user.return_value = user
        request = RequestFactory().get(
            '/',
            HTTP_AUTHORIZATION='Bearer clerk-session-token',
        )

        result = ClerkAuthentication().authenticate(request)

        self.assertEqual(result, (user, {'sub': 'user_clerk_123'}))
        verify_token.assert_called_once_with('clerk-session-token')
        sync_user.assert_called_once_with('user_clerk_123')

    @override_settings(
        CLERK_ISSUER='https://example.clerk.accounts.dev',
        CLERK_JWKS_URL='https://example.clerk.accounts.dev/.well-known/jwks.json',
        CLERK_AUTHORIZED_PARTIES=['http://localhost:5173'],
    )
    @patch('users.authentication.jwt.decode')
    @patch('users.authentication.jwt.PyJWKClient')
    def test_wrong_authorized_party_is_rejected(self, jwks_client, decode):
        jwks_client.return_value.get_signing_key_from_jwt.return_value = type(
            'SigningKey',
            (),
            {'key': 'public-key'},
        )()
        decode.return_value = {
            'sub': 'user_clerk_123',
            'azp': 'https://attacker.example',
        }

        with self.assertRaises(AuthenticationFailed):
            verify_clerk_token(b'clerk-session-token')

    @override_settings(
        CLERK_ISSUER='',
        CLERK_JWKS_URL='',
        CLERK_AUTHORIZED_PARTIES=[],
    )
    def test_missing_clerk_settings_raise_a_clear_api_configuration_error(self):
        with self.assertRaises(ClerkConfigurationError) as error:
            verify_clerk_token('clerk-session-token')

        self.assertEqual(error.exception.status_code, 503)


class MeViewTests(TestCase):
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
