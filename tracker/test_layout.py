from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class BaseLayoutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username='layout-user',
            first_name='Иван',
            last_name='Петров',
            password='Layout-pass-123!',
        )

    def test_authenticated_page_uses_shared_layout(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('tracker:home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tracker/base.html')
        self.assertContains(response, 'Жир')
        self.assertContains(response, 'Иван Петров')
        self.assertContains(response, 'aria-label="Основная навигация"')
        for label in ['Dashboard', 'Компании', 'Команды', 'Мои задачи']:
            self.assertContains(response, label)
        self.assertContains(response, 'method="post"')
        self.assertContains(response, reverse('tracker:logout'))

    def test_guest_auth_pages_use_layout_without_sidebar(self):
        for name in ['tracker:login', 'tracker:register']:
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, 'tracker/base.html')
                self.assertNotContains(response, 'app-sidebar')
                self.assertContains(response, 'auth-card')

    def test_bootstrap_and_project_css_are_loaded_in_order(self):
        response = self.client.get(reverse('tracker:login'))
        content = response.content.decode()
        bootstrap = 'bootstrap@5.3.8/dist/css/bootstrap.min.css'
        project_css = '/static/tracker/css/style.css'
        self.assertIn(bootstrap, content)
        self.assertIn(
            'sha384-sRIl4kxILFvY47J16cr9ZwB07vP4J8+LH7qKQnuqkuIAvNWLzeN8tE5YBujZqJLB',
            content,
        )
        self.assertIn('bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js', content)
        self.assertLess(content.index(bootstrap), content.index(project_css))

    def test_authentication_fields_have_bootstrap_classes(self):
        for name in ['tracker:login', 'tracker:register']:
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                for field in response.context['form'].fields.values():
                    self.assertIn('form-control', field.widget.attrs.get('class', ''))

    def test_base_template_exposes_required_blocks(self):
        template = (
            Path(settings.BASE_DIR) / 'tracker/templates/tracker/base.html'
        ).read_text(encoding='utf-8')
        self.assertIn('{% block content %}', template)
        self.assertIn('{% block auth_content %}', template)
        self.assertIn('{% block scripts %}', template)
        self.assertIn('{% block extra_head %}', template)
