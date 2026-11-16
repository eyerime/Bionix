from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Document, ReadingSession
from .views import _fmt_duration

User = get_user_model()


class FormatDurationTests(TestCase):
    def test_formats(self):
        self.assertEqual(_fmt_duration(45), '45s')
        self.assertEqual(_fmt_duration(125), '2m 5s')
        self.assertEqual(_fmt_duration(3720), '1h 2m')


class HistoryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('h1', 'h1@example.com', 'pw-12345-xyz')
        self.client.login(username='h1', password='pw-12345-xyz')
        self.doc = Document.objects.create(
            user=self.user, title='Moby Dick', file_path='x', file_type='txt', word_count=500)

    def _session(self, user=None, doc=None, minutes_ago=0, duration=60, words=100, wpm=100):
        return ReadingSession.objects.create(
            user=user or self.user, document=doc or self.doc,
            started_at=timezone.now() - timedelta(minutes=minutes_ago),
            duration_seconds=duration, words_read=words, reading_speed_wpm=wpm)

    def test_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse('dashboard:history'))
        self.assertEqual(resp.status_code, 302)

    def test_empty_state(self):
        resp = self.client.get(reverse('dashboard:history'))
        self.assertContains(resp, 'No reading sessions yet')

    def test_lists_own_sessions_with_totals(self):
        self._session(duration=60, words=100)
        self._session(minutes_ago=5, duration=120, words=300, wpm=150)
        resp = self.client.get(reverse('dashboard:history'))
        self.assertContains(resp, 'Moby Dick', count=2)
        self.assertContains(resp, '3m 0s')                       # 180s total
        self.assertEqual(resp.context['session_count'], 2)
        self.assertEqual(resp.context['total_words'], 400)
        self.assertEqual(resp.context['total_time'], '3m 0s')

    def test_excludes_other_users_and_empty_sessions(self):
        other = User.objects.create_user('h2', 'h2@example.com', 'pw-12345-xyz')
        od = Document.objects.create(user=other, title='Secret', file_path='o', file_type='txt')
        self._session(user=other, doc=od)
        self._session(duration=0)          # opened but never read
        resp = self.client.get(reverse('dashboard:history'))
        self.assertNotContains(resp, 'Secret')
        self.assertEqual(resp.context['session_count'], 0)

    def test_pagination(self):
        for i in range(20):
            self._session(minutes_ago=i)
        resp = self.client.get(reverse('dashboard:history'))
        self.assertEqual(len(resp.context['rows']), 15)
        resp = self.client.get(reverse('dashboard:history') + '?page=2')
        self.assertEqual(len(resp.context['rows']), 5)

    def test_dash_shown_when_no_speed(self):
        self._session(wpm=0)
        resp = self.client.get(reverse('dashboard:history'))
        self.assertNotContains(resp, ' wpm')

    def test_nav_link_present(self):
        resp = self.client.get(reverse('dashboard:home'))
        self.assertContains(resp, reverse('dashboard:history'))
