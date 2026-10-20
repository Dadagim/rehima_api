from rest_framework import permissions
from rest_framework.permissions import SAFE_METHODS


def is_staff_user(user):
    if not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    return getattr(getattr(user, 'profile', None), 'role', None) in {
        'coach',
        'casher',
        'admin',
    }


class StaffOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        return is_staff_user(request.user)


class MemberProfileAccess(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, profile):
        if is_staff_user(request.user):
            return True
        return request.method in SAFE_METHODS and profile.user_id == request.user.pk
