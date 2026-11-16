import json
import shutil
import tempfile
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile, UserStats

from .models import Document, ReadingProgress, ReadingSession
from .reading import bionize, clamp_intensity
from .stats import _streaks, recalculate_stats

User = get_user_model()
TMP_MEDIA = tempfile.mkdtemp()


class BionizeTests(SimpleTestCase):
    def test_bolds_leading_letters(self):
        self.assertEqual(bionize('reading', 0.5), '<p><b>read</b>ing</p>')

    def test_short_words_get_at_least_one_bold_letter(self):
        self.assertEqual(bionize('a I', 0.1), '<p><b>a</b> <b>I</b></p>')

    def test_higher_intensity_bolds_more(self):
        self.assertEqual(bionize('reading', 0.6), '<p><b>readi</b>ng</p>')

    def test_escapes_html(self):
        out = bionize('<script>alert(1)</script>')
        self.assertNotIn('<script>', out)
        self.assertIn('&lt;', out)

    def test_paragraphs_and_line_breaks(self):
        out = bionize('one\ntwo\n\nthree')
        self.assertEqual(out.count('<p>'), 2)
        self.assertIn('<br>', out)

    def test_empty_text(self):
        self.assertEqual(bionize('   '), '')

    def test_clamp(self):
        self.assertEqual(clamp_intensity(5), 0.9)
        self.assertEqual(clamp_intensity(-1), 0.1)
        self.assertEqual(clamp_intensity('junk'), 0.5)


class StreakTests(SimpleTestCase):
    def test_streaks(self):
        today = timezone.localdate()
        d = lambda n: today - timedelta(days=n)
        self.assertEqual(_streaks(set()), (0, 0))
        self.assertEqual(_streaks({d(0), d(1), d(2)}), (3, 3))
        self.assertEqual(_streaks({d(1), d(2)}), (2, 2))          # yesterday still counts
        self.assertEqual(_streaks({d(5), d(6), d(7)}), (0, 3))    # broken streak
        self.assertEqual(_streaks({d(0), d(2), d(3), d(4)}), (1, 3))


@override_settings(MEDIA_ROOT=TMP_MEDIA)
class ReaderTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.user = User.objects.create_user('r1', 'r1@example.com', 'pw-12345-xyz')
        self.client.login(username='r1', password='pw-12345-xyz')
        text = ' '.join(['reading'] * 1000)
        path = default_storage.save('documents/test/doc.txt', ContentFile(text.encode()))
        self.doc = Document.objects.create(
            user=self.user, title='Doc', file_path=path, file_type='txt', word_count=1000)
        ReadingProgress.objects.create(document=self.doc)

    def _progress(self, percent, **extra):
        body = {'percent': percent, 'start_percent': 0, 'furthest': percent}
        body.update(extra)
        return self.client.post(reverse('dashboard:save_progress', args=[self.doc.pk]),
                                json.dumps(body), content_type='application/json')

    def test_reader_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse('dashboard:reader', args=[self.doc.pk]))
        self.assertEqual(resp.status_code, 302)

    def test_reader_renders_bionic_text_and_creates_session(self):
        resp = self.client.get(reverse('dashboard:reader', args=[self.doc.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '<b>read</b>ing')
        self.assertEqual(ReadingSession.objects.filter(user=self.user).count(), 1)
        self.doc.refresh_from_db()
        self.assertIsNotNone(self.doc.last_opened_at)

    def test_cannot_open_other_users_document(self):
        other = User.objects.create_user('r2', 'r2@example.com', 'pw-12345-xyz')
        d = Document.objects.create(user=other, title='x', file_path='x', file_type='txt')
        resp = self.client.get(reverse('dashboard:reader', args=[d.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_missing_file_redirects_to_dashboard(self):
        self.doc.file_path = 'documents/test/gone.txt'
        self.doc.save()
        resp = self.client.get(reverse('dashboard:reader', args=[self.doc.pk]))
        self.assertRedirects(resp, reverse('dashboard:home'))

    def test_progress_updates_status_and_keeps_furthest(self):
        self.assertEqual(self._progress(40).status_code, 200)
        p = ReadingProgress.objects.get(document=self.doc)
        self.assertEqual((float(p.progress_percent), p.status), (40.0, 'in_progress'))
        self._progress(25)                       # scrolled back up
        p.refresh_from_db()
        self.assertEqual(float(p.progress_percent), 40.0)
        self.assertEqual(p.current_position, 2500)   # resume point follows the user

    def test_progress_marks_completed(self):
        self._progress(99)
        p = ReadingProgress.objects.get(document=self.doc)
        self.assertEqual(p.status, 'completed')
        self.assertEqual(UserStats.objects.get(user=self.user).documents_read_count, 1)

    def test_progress_rejects_bad_json(self):
        resp = self.client.post(reverse('dashboard:save_progress', args=[self.doc.pk]),
                                'not json', content_type='application/json')
        self.assertEqual(resp.status_code, 400)

    def test_progress_updates_session_and_stats(self):
        session = ReadingSession.objects.create(
            user=self.user, document=self.doc,
            started_at=timezone.now() - timedelta(seconds=120))
        self._progress(50, session_id=session.session_id)
        session.refresh_from_db()
        self.assertEqual(session.words_read, 500)
        self.assertGreaterEqual(session.duration_seconds, 120)
        self.assertTrue(0 < session.reading_speed_wpm <= 1200)
        stats = UserStats.objects.get(user=self.user)
        self.assertEqual(stats.avg_reading_speed_wpm, session.reading_speed_wpm)
        self.assertEqual(stats.current_streak_days, 1)

    def test_other_users_session_is_ignored(self):
        other = User.objects.create_user('r3', 'r3@example.com', 'pw-12345-xyz')
        od = Document.objects.create(user=other, title='o', file_path='o', file_type='txt')
        s = ReadingSession.objects.create(user=other, document=od, started_at=timezone.now())
        self._progress(50, session_id=s.session_id)
        s.refresh_from_db()
        self.assertEqual(s.words_read, 0)

    def test_settings_saved_and_clamped(self):
        resp = self.client.post(
            reverse('dashboard:reader_settings', args=[self.doc.pk]),
            {'theme': 'light', 'font_size': 'xl', 'fixation_intensity': '7', 'percent': '33.5'})
        self.assertRedirects(resp, reverse('dashboard:reader', args=[self.doc.pk]))
        prof = UserProfile.objects.get(user=self.user)
        self.assertEqual(prof.theme_preference, 'light')
        self.assertEqual(prof.font_size_pref, 'xl')
        self.assertEqual(float(prof.fixation_intensity), 0.9)
        self.assertEqual(ReadingProgress.objects.get(document=self.doc).current_position, 3350)

    def test_settings_ignore_invalid_choices(self):
        self.client.post(reverse('dashboard:reader_settings', args=[self.doc.pk]),
                         {'theme': 'neon', 'font_size': 'huge'})
        prof = UserProfile.objects.get(user=self.user)
        self.assertEqual((prof.theme_preference, prof.font_size_pref), ('dark', 'md'))

    def test_new_settings_change_rendering(self):
        self.client.post(reverse('dashboard:reader_settings', args=[self.doc.pk]),
                         {'theme': 'light', 'font_size': 'lg', 'fixation_intensity': '0.6'})
        resp = self.client.get(reverse('dashboard:reader', args=[self.doc.pk]))
        self.assertContains(resp, 'data-theme="light"')
        self.assertContains(resp, 'font-lg')
        self.assertContains(resp, '<b>readi</b>ng')

    def test_resume_position(self):
        self._progress(60)
        resp = self.client.get(reverse('dashboard:reader', args=[self.doc.pk]))
        self.assertContains(resp, 'var startPercent = 60.00;')

    def test_recalculate_stats_time_saved(self):
        ReadingSession.objects.create(
            user=self.user, document=self.doc, started_at=timezone.now(),
            duration_seconds=300, words_read=2000, reading_speed_wpm=400)
        stats = recalculate_stats(self.user)
        # 2000 words at 238 wpm ~ 504s; reading took 300s => ~204s saved => 3 min
        self.assertEqual(stats.total_time_saved_min, 3)
