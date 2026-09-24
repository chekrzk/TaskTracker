from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .models import Company, Product, Team, TeamMember


class CompanyViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.owner = users.objects.create_user(username='owner', password='Pass-12345!')
        cls.member = users.objects.create_user(username='member', password='Pass-12345!')
        cls.outsider = users.objects.create_user(username='outsider', password='Pass-12345!')
        cls.other_owner = users.objects.create_user(
            username='other-owner', password='Pass-12345!',
        )

        cls.company = Company.objects.create(
            name='Accessible Company',
            description='Company description',
            owner=cls.owner,
        )
        cls.member_product = Product.objects.create(
            company=cls.company,
            name='Member Product',
            description='Visible product',
        )
        cls.member_team = Team.objects.create(name='Backend', product=cls.member_product)
        TeamMember.objects.create(team=cls.member_team, user=cls.member)
        cls.hidden_product = Product.objects.create(
            company=cls.company,
            name='Hidden Product',
            description='Owner only',
        )
        Team.objects.create(name='Internal', product=cls.hidden_product)
        cls.private_company = Company.objects.create(
            name='Private Company', owner=cls.other_owner,
        )

    def test_company_pages_require_authentication(self):
        urls = [
            reverse('tracker:company_list'),
            reverse('tracker:company_create'),
            reverse('tracker:company_detail', args=[self.company.pk]),
            reverse('tracker:company_edit', args=[self.company.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertRedirects(
                    self.client.get(url),
                    f"{reverse('tracker:login')}?next={url}",
                )

    def test_list_contains_owned_and_team_companies_only(self):
        cases = [
            (self.owner, ['Accessible Company'], ['Private Company']),
            (self.member, ['Accessible Company'], ['Private Company']),
            (self.outsider, [], ['Accessible Company', 'Private Company']),
        ]
        for user, visible, hidden in cases:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(reverse('tracker:company_list'))
                self.assertEqual(response.status_code, 200)
                for name in visible:
                    self.assertContains(response, name)
                for name in hidden:
                    self.assertNotContains(response, name)

    def test_create_sets_current_user_as_owner_and_ignores_posted_owner(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('tracker:company_create'), {
            'name': 'Created Company',
            'description': 'Created from form',
            'owner': self.other_owner.pk,
        })
        company = Company.objects.get(name='Created Company')
        self.assertEqual(company.owner, self.member)
        self.assertRedirects(
            response, reverse('tracker:company_detail', args=[company.pk]),
        )

    def test_create_rejects_empty_name(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse('tracker:company_create'), {
            'name': '   ', 'description': 'Invalid',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('name', response.context['form'].errors)
        self.assertFalse(Company.objects.filter(description='Invalid').exists())

    def test_owner_sees_all_products_and_can_edit(self):
        self.client.force_login(self.owner)
        detail = self.client.get(
            reverse('tracker:company_detail', args=[self.company.pk]),
        )
        self.assertContains(detail, 'Member Product')
        self.assertContains(detail, 'Hidden Product')
        self.assertContains(detail, 'Редактировать')

        response = self.client.post(
            reverse('tracker:company_edit', args=[self.company.pk]),
            {'name': 'Renamed Company', 'description': 'Updated'},
        )
        self.assertRedirects(
            response, reverse('tracker:company_detail', args=[self.company.pk]),
        )
        self.company.refresh_from_db()
        self.assertEqual(self.company.name, 'Renamed Company')
        self.assertEqual(self.company.owner, self.owner)

    def test_team_member_sees_only_accessible_products_and_cannot_edit(self):
        self.client.force_login(self.member)
        detail_url = reverse('tracker:company_detail', args=[self.company.pk])
        detail = self.client.get(detail_url)
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, 'Member Product')
        self.assertNotContains(detail, 'Hidden Product')
        self.assertNotContains(detail, 'Редактировать')
        edit_url = reverse('tracker:company_edit', args=[self.company.pk])
        self.assertEqual(self.client.get(edit_url).status_code, 403)
        self.assertEqual(
            self.client.post(edit_url, {'name': 'Hack'}).status_code,
            403,
        )

    def test_outsider_gets_403_and_missing_company_gets_404(self):
        self.client.force_login(self.outsider)
        for name in ['tracker:company_detail', 'tracker:company_edit']:
            with self.subTest(name=name):
                self.assertEqual(
                    self.client.get(reverse(name, args=[self.company.pk])).status_code,
                    403,
                )
                self.assertEqual(
                    self.client.get(reverse(name, args=[999999])).status_code,
                    404,
                )

    def test_company_forms_require_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(
            client.post(
                reverse('tracker:company_create'), {'name': 'No CSRF'},
            ).status_code,
            403,
        )
        self.assertEqual(
            client.post(
                reverse('tracker:company_edit', args=[self.company.pk]),
                {'name': 'No CSRF'},
            ).status_code,
            403,
        )

    def test_company_navigation_is_active(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('tracker:company_list'))
        self.assertContains(response, 'href="/companies/">Компании</a>', html=False)
        self.assertNotContains(response, 'Компаний пока нет')
