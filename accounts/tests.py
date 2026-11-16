from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import UserProfile, UserStats

User = get_user_model()


class AuthFlowTests(TestCase):
    def test_register_creates_user_profile_and_stats_and_logs_in(self):
        resp = self.client.post(reverse('accounts:register'), {
            'username': 'reader1', 'email': 'Reader1@Example.com',
            'password1': 'Str0ng-pass-123', 'password2': 'Str0ng-pass-123',
        })
        self.assertRedirects(resp, reverse('dashboard:home'))
        user = User.objects.get(username='reader1')
        self.assertEqual(user.email, 'reader1@example.com')
        self.assertTrue(UserProfile.objects.filter(user=user).exists())
        self.assertTrue(UserStats.objects.filter(user=user).exists())
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

    def test_register_rejects_duplicate_email(self):
        User.objects.create_user('a', 'dup@example.com', 'x')
        resp = self.client.post(reverse('accounts:register'), {
            'username': 'b', 'email': 'dup@example.com',
            'password1': 'Str0ng-pass-123', 'password2': 'Str0ng-pass-123',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(username='b').exists())

    def test_login_and_logout(self):
        User.objects.create_user('reader2', 'r2@example.com', 'Str0ng-pass-123')
        resp = self.client.post(reverse('accounts:login'),
                                {'username': 'reader2', 'password': 'Str0ng-pass-123'})
        self.assertRedirects(resp, reverse('dashboard:home'))
        resp = self.client.post(reverse('accounts:logout'))
        self.assertRedirects(resp, reverse('accounts:login'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_bad_login_shows_error(self):
        resp = self.client.post(reverse('accounts:login'),
                                {'username': 'nobody', 'password': 'nope'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'alert-error')

    def test_pages_render(self):
        self.assertEqual(self.client.get(reverse('accounts:login')).status_code, 200)
        self.assertEqual(self.client.get(reverse('accounts:register')).status_code, 200)
