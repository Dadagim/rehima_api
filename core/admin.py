from django.contrib import admin
from django.contrib.auth.models import User
from .models import *


class AdminUser(admin.ModelAdmin):
    list_display = ('id','username', 'email')



class AdminCoinTransaction(admin.ModelAdmin):
    list_display = ('id','user', 'transaction_type', 'amount')


class AdminMemberShipPlan(admin.ModelAdmin):
    list_display = ('id','name', 'duration', 'price')

class AdminMembership(admin.ModelAdmin):
    list_display = ('id','user', 'qr_token', 'start_date', 'end_date', 'is_active')

class AdminCheckIn(admin.ModelAdmin):
    list_display = ('id', 'user', 'membership', 'is_successful', 'created_at')


admin.site.register(CoinTransaction, AdminCoinTransaction)
admin.site.register(MemberShipPlans, AdminMemberShipPlan)
admin.site.register(MemberShip, AdminMembership)
admin.site.register(CheckIn, AdminCheckIn)
