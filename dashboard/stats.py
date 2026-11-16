"""Recalculate a user's aggregated reading stats from their sessions."""
from datetime import timedelta

from django.utils import timezone

from accounts.models import UserStats

from .models import ReadingProgress, ReadingSession

NORMAL_WPM = 238          # average adult silent-reading speed (baseline for "time saved")
MIN_STREAK_SECONDS = 30   # a session shorter than this does not count as a reading day


def _streaks(days):
    """Return (current_streak, longest_streak) from a set of dates."""
    if not days:
        return 0, 0
    ordered = sorted(days)
    longest = run = 1
    for prev, cur in zip(ordered, ordered[1:]):
        run = run + 1 if cur - prev == timedelta(days=1) else 1
        longest = max(longest, run)

    today = timezone.localdate()
    last = ordered[-1]
    if last < today - timedelta(days=1):
        return 0, longest
    current = 1
    for i in range(len(ordered) - 1, 0, -1):
        if ordered[i] - ordered[i - 1] == timedelta(days=1):
            current += 1
        else:
            break
    return current, longest


def recalculate_stats(user):
    stats, _ = UserStats.objects.get_or_create(user=user)
    sessions = list(ReadingSession.objects.filter(user=user))

    speeds = [s.reading_speed_wpm for s in sessions if s.reading_speed_wpm > 0]
    stats.avg_reading_speed_wpm = round(sum(speeds) / len(speeds)) if speeds else 0

    # Time saved = time the user would have needed at a normal pace minus the time
    # they actually spent. Only sessions long enough to yield a valid speed count,
    # so opening a document for a second cannot inflate the number.
    saved_seconds = 0
    for s in sessions:
        if s.reading_speed_wpm > NORMAL_WPM and s.duration_seconds > 0:
            saved_seconds += s.duration_seconds * (s.reading_speed_wpm / NORMAL_WPM - 1)
    stats.total_time_saved_min = int(saved_seconds // 60)

    stats.documents_read_count = ReadingProgress.objects.filter(
        document__user=user, status='completed').count()

    days = {timezone.localtime(s.started_at).date()
            for s in sessions if s.duration_seconds >= MIN_STREAK_SECONDS}
    stats.current_streak_days, longest = _streaks(days)
    stats.longest_streak_days = max(stats.longest_streak_days, longest)

    stats.last_calculated_at = timezone.now()
    stats.save()
    return stats
