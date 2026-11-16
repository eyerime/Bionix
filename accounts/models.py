"""
BionixReader - accounts/models.py  (vertical slice: user account data)

ERD entity        -> Django model / table
---------------------------------------------------------------
USERS (auth_user) -> django.contrib.auth.models.User  (built-in, auth_user)
USER_PROFILES     -> UserProfile      (user_profiles)
USER_STATS        -> UserStats        (user_stats)

Relationships
---------------------------------------------------------------
USERS 1 - 1 USER_PROFILES   (OneToOneField, unique FK)
USERS 1 - 1 USER_STATS      (OneToOneField, unique FK)
"""

from django.conf import settings
from django.db import models

# USERS (auth_user) is Django's built-in User model. Referencing it through
# settings.AUTH_USER_MODEL keeps the FKs pointed at the auth_user table.
User = settings.AUTH_USER_MODEL


class UserProfile(models.Model):
    """USER_PROFILES - reader display preferences (1-1 with USERS)."""

    profile_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(
        User, on_delete=models.CASCADE,
        db_column='user_id', related_name='profile',
    )
    theme_preference = models.CharField(max_length=20, default='dark')
    fixation_intensity = models.DecimalField(max_digits=3, decimal_places=2, default=0.50)
    font_size_pref = models.CharField(max_length=10, default='md')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_profiles'

    def __str__(self):
        return f'Profile of {self.user}'


class UserStats(models.Model):
    """USER_STATS - aggregated reading statistics (1-1 with USERS)."""

    stat_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(
        User, on_delete=models.CASCADE,
        db_column='user_id', related_name='stats',
    )
    documents_read_count = models.IntegerField(default=0)
    avg_reading_speed_wpm = models.IntegerField(default=0)
    total_time_saved_min = models.IntegerField(default=0)
    current_streak_days = models.IntegerField(default=0)
    longest_streak_days = models.IntegerField(default=0)
    last_calculated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'user_stats'
        verbose_name_plural = 'user stats'

    def __str__(self):
        return f'Stats of {self.user}'
