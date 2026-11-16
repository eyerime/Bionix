from django.contrib import admin

from .models import UserProfile, UserStats


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'theme_preference', 'fixation_intensity', 'font_size_pref')


@admin.register(UserStats)
class UserStatsAdmin(admin.ModelAdmin):
    list_display = ('user', 'documents_read_count', 'avg_reading_speed_wpm',
                    'current_streak_days', 'longest_streak_days')
