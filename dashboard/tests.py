import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import UserStats

from .models import Document, ReadingProgress

User = get_user_model()
TMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TMP_MEDIA)
class DashboardTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.user = User.objects.create_user('u1', 'u1@example.com', 'pw-12345-xyz')
        self.client.login(username='u1', password='pw-12345-xyz')

    def _upload(self, name='story.txt', content=b'one two three four five', title=''):
        return self.client.post(reverse('dashboard:upload'), {
            'title': title, 'file': SimpleUploadedFile(name, content)})

    def test_dashboard_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse('dashboard:home'))
        self.assertRedirects(resp, f"{reverse('accounts:login')}?next=/")

    def test_dashboard_empty_state_and_stats_row_created(self):
        resp = self.client.get(reverse('dashboard:home'))
        self.assertContains(resp, 'No documents yet')
        self.assertTrue(UserStats.objects.filter(user=self.user).exists())

    def test_upload_txt_creates_document_and_progress(self):
        resp = self._upload()
        self.assertRedirects(resp, reverse('dashboard:home'))
        doc = Document.objects.get(user=self.user)
        self.assertEqual(doc.title, 'story')
        self.assertEqual(doc.word_count, 5)
        self.assertEqual(doc.file_type, 'txt')
        self.assertEqual(doc.progress.status, 'not_started')
        self.assertContains(self.client.get(reverse('dashboard:home')), 'story')

    def test_upload_custom_title(self):
        self._upload(title='My Title')
        self.assertEqual(Document.objects.get().title, 'My Title')

    def test_upload_rejects_bad_extension(self):
        resp = self._upload(name='virus.exe')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Document.objects.count(), 0)

    def test_upload_rejects_empty_file(self):
        resp = self._upload(content=b'')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Document.objects.count(), 0)

    def test_delete_own_document(self):
        self._upload()
        doc = Document.objects.get()
        resp = self.client.post(reverse('dashboard:delete_document', args=[doc.pk]))
        self.assertRedirects(resp, reverse('dashboard:home'))
        self.assertEqual(Document.objects.count(), 0)
        self.assertEqual(ReadingProgress.objects.count(), 0)

    def test_cannot_delete_other_users_document(self):
        other = User.objects.create_user('u2', 'u2@example.com', 'pw-12345-xyz')
        doc = Document.objects.create(user=other, title='x', file_path='x', file_type='txt')
        resp = self.client.post(reverse('dashboard:delete_document', args=[doc.pk]))
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(Document.objects.count(), 1)

    def test_delete_requires_post(self):
        doc = Document.objects.create(user=self.user, title='x', file_path='x', file_type='txt')
        resp = self.client.get(reverse('dashboard:delete_document', args=[doc.pk]))
        self.assertEqual(resp.status_code, 405)
