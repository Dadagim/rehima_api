import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from rest_framework.exceptions import APIException, AuthenticationFailed

from .models import UserProfile


class AccountLinkConflict(APIException):
    status_code = 409
    default_detail = (
        'This Clerk account could not be linked to one unique existing account. '
        'Please contact an administrator.'
    )
    default_code = 'account_link_conflict'


class ClerkServiceUnavailable(APIException):
    status_code = 503
    default_detail = 'Clerk user data is temporarily unavailable.'
    default_code = 'clerk_unavailable'


class ClerkConfigurationError(APIException):
    status_code = 503
    default_detail = 'Clerk authentication is not configured on this server.'
    default_code = 'clerk_not_configured'


def fetch_clerk_user(clerk_id):
    if not settings.CLERK_SECRET_KEY:
        raise ClerkConfigurationError(
            'Configure CLERK_SECRET_KEY in config/.env to provision Clerk users.'
        )

    request = Request(
        f'https://api.clerk.com/v1/users/{quote(clerk_id, safe="")}',
        headers={'Authorization': f'Bearer {settings.CLERK_SECRET_KEY}'},
    )
    try:
        with urlopen(request, timeout=5) as response:
            identity = json.loads(response.read())
    except HTTPError as exc:
        if exc.code == 404:
            raise AuthenticationFailed('The Clerk account no longer exists.') from exc
        if exc.code in {401, 403}:
            raise ClerkConfigurationError('CLERK_SECRET_KEY was rejected by Clerk.') from exc
        raise ClerkServiceUnavailable() from exc
    except (URLError, TimeoutError) as exc:
        raise ClerkServiceUnavailable() from exc
    except json.JSONDecodeError as exc:
        raise ClerkServiceUnavailable('Clerk returned an invalid user response.') from exc

    if not isinstance(identity, dict) or identity.get('id') != clerk_id:
        raise AuthenticationFailed('Clerk returned an unexpected user identity.')
    return identity


def _verified_email(identity):
    addresses = identity.get('email_addresses', [])
    primary_id = identity.get('primary_email_address_id')
    verified = [
        item['email_address']
        for item in addresses
        if item.get('verification', {}).get('status') == 'verified'
        and item.get('email_address')
    ]
    if not verified:
        return ''
    for item in addresses:
        if (
            item.get('id') == primary_id
            and item.get('verification', {}).get('status') == 'verified'
        ):
            return item['email_address']
    return verified[0]


def _username_for(identity, clerk_id, email):
    source = identity.get('username') or (email.split('@', 1)[0] if email else '') or clerk_id
    base = re.sub(r'[^A-Za-z0-9.@+-]', '-', source).strip('.@+-') or clerk_id
    base = base[:150]
    if not User.objects.filter(username=base).exists():
        return base

    suffix = clerk_id[-12:]
    candidate = f'{base[:137]}-{suffix}'
    counter = 1
    while User.objects.filter(username=candidate).exists():
        counter += 1
        counter_suffix = f'-{suffix}-{counter}'
        candidate = f'{base[:150 - len(counter_suffix)]}{counter_suffix}'
    return candidate


def _primary_phone_number(identity):
    phones = identity.get('phone_numbers', [])
    primary_id = identity.get('primary_phone_number_id')
    for phone in phones:
        if phone.get('id') == primary_id and phone.get('phone_number'):
            return phone['phone_number']
    return ''


def sync_clerk_user(clerk_id):
    linked_profile = (
        UserProfile.objects.select_related('user').filter(clerk_id=clerk_id).first()
    )
    if linked_profile:
        return linked_profile.user

    identity = fetch_clerk_user(clerk_id)
    email = _verified_email(identity)
    first_name = (identity.get('first_name') or '')[:150]
    last_name = (identity.get('last_name') or '')[:150]
    full_name = ' '.join(part for part in (first_name, last_name) if part)[:100]
    phone_number = _primary_phone_number(identity)[:20]

    try:
        with transaction.atomic():
            linked_profile = (
                UserProfile.objects.select_related('user')
                .select_for_update()
                .filter(clerk_id=clerk_id)
                .first()
            )
            if linked_profile:
                return linked_profile.user

            candidates = list(
                User.objects.filter(email__iexact=email).order_by('pk')[:2]
            ) if email else []
            if len(candidates) > 1:
                raise AccountLinkConflict()
            user = candidates[0] if candidates else None

            profile = None
            if user:
                profile = UserProfile.objects.select_for_update().filter(user=user).first()
                if profile and profile.clerk_id and profile.clerk_id != clerk_id:
                    raise AccountLinkConflict()
            else:
                user = User.objects.create_user(
                    username=_username_for(identity, clerk_id, email),
                    email=email,
                    password=None,
                    first_name=first_name,
                    last_name=last_name,
                )

            if not profile:
                profile = UserProfile(user=user)
            profile.clerk_id = clerk_id
            if not profile.full_name and full_name:
                profile.full_name = full_name
            if not profile.phone_number and phone_number:
                profile.phone_number = phone_number
            profile.save()
            return user
    except IntegrityError as exc:
        linked_profile = (
            UserProfile.objects.select_related('user').filter(clerk_id=clerk_id).first()
        )
        if linked_profile:
            return linked_profile.user
        raise AccountLinkConflict() from exc
