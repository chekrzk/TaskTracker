from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse


class AuthenticationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='existing',
            email='existing@example.com',
            password='Existing-pass-123!',
        )

    def register_data(self, **changes):
        data = {
            'username': 'new-user',
            'email': 'New.User@example.com',
            'first_name': 'Новый',
            'last_name': 'Пользователь',
            'password1': 'Strong-pass-583!',
            'password2': 'Strong-pass-583!',
        }
        data.update(changes)
        return data

    def test_guest_is_redirected_from_home_to_login(self):
        response = self.client.get(reverse('tracker:home'))
        self.assertRedirects(
            response,
            f"{reverse('tracker:login')}?next={reverse('tracker:home')}",
        )

    def test_registration_page_is_available(self):
        response = self.client.get(reverse('tracker:register'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Регистрация')
        self.assertContains(response, 'csrfmiddlewaretoken')

    def test_registration_creates_user_hashes_password_and_logs_in(self):
        response = self.client.post(reverse('tracker:register'), self.register_data())
        self.assertRedirects(response, reverse('tracker:home'))
        user = get_user_model().objects.get(username='new-user')
        self.assertEqual(user.email, 'new.user@example.com')
        self.assertEqual(user.first_name, 'Новый')
        self.assertTrue(user.check_password('Strong-pass-583!'))
        self.assertNotEqual(user.password, 'Strong-pass-583!')
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

    def test_registration_rejects_duplicate_email_case_insensitively(self):
        response = self.client.post(
            reverse('tracker:register'),
            self.register_data(email='EXISTING@example.com'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context['form'],
            'email',
            'Пользователь с таким email уже существует.',
        )
        self.assertFalse(get_user_model().objects.filter(username='new-user').exists())

    def test_registration_rejects_bad_password_and_mismatch(self):
        cases = [
            ({'password1': '123', 'password2': '123'}, 'password2'),
            ({'password2': 'Different-pass-583!'}, 'password2'),
        ]
        for changes, field in cases:
            with self.subTest(changes=changes):
                response = self.client.post(
                    reverse('tracker:register'), self.register_data(**changes),
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn(field, response.context['form'].errors)
                self.assertFalse(
                    get_user_model().objects.filter(username='new-user').exists(),
                )

    def test_authenticated_user_is_redirected_away_from_auth_pages(self):
        self.client.force_login(self.user)
        for name in ['tracker:register', 'tracker:login']:
            with self.subTest(name=name):
                self.assertRedirects(self.client.get(reverse(name)), reverse('tracker:home'))

    def test_login_accepts_valid_credentials_and_rejects_invalid_ones(self):
        login_url = reverse('tracker:login')
        invalid = self.client.post(login_url, {
            'username': 'existing', 'password': 'wrong-password',
        })
        self.assertEqual(invalid.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

        valid = self.client.post(login_url, {
            'username': 'existing', 'password': 'Existing-pass-123!',
        })
        self.assertRedirects(valid, reverse('tracker:home'))
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)

    def test_login_honors_local_next_and_rejects_external_next(self):
        login_url = reverse('tracker:login')
        local = self.client.post(login_url, {
            'username': 'existing',
            'password': 'Existing-pass-123!',
            'next': reverse('tracker:home'),
        })
        self.assertRedirects(local, reverse('tracker:home'))

        self.client.logout()
        external = self.client.post(login_url, {
            'username': 'existing',
            'password': 'Existing-pass-123!',
            'next': 'https://example.com/phishing',
        })
        self.assertRedirects(external, reverse('tracker:home'))

    def test_logout_requires_post_and_ends_session(self):
        self.client.force_login(self.user)
        logout_url = reverse('tracker:logout')
        self.assertEqual(self.client.get(logout_url).status_code, 405)
        response = self.client.post(logout_url)
        self.assertRedirects(response, reverse('tracker:login'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_authentication_posts_require_csrf_token(self):
        csrf_client = Client(enforce_csrf_checks=True)
        for name, data in [
            ('tracker:register', self.register_data()),
            ('tracker:login', {
                'username': 'existing', 'password': 'Existing-pass-123!',
            }),
        ]:
            with self.subTest(name=name):
                self.assertEqual(csrf_client.post(reverse(name), data).status_code, 403)

        csrf_client.force_login(self.user)
        self.assertEqual(
            csrf_client.post(reverse('tracker:logout')).status_code,
            403,
        )
