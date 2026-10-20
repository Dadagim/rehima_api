from django.contrib import admin
from .models import *


class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['id', 'full_name', 'phone_number', 'role', 'clerk_id']

admin.site.register(UserProfile, UserProfileAdmin)