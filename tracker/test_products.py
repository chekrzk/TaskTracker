from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .models import Company, Product, Team, TeamMember


class ProductViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.owner = users.objects.create_user(username='owner-p', password='Pass-12345!')
        cls.member = users.objects.create_user(username='member-p', password='Pass-12345!')
        cls.other_member = users.objects.create_user(username='other-member-p', password='Pass-12345!')
        cls.outsider = users.objects.create_user(username='outsider-p', password='Pass-12345!')
        cls.other_owner = users.objects.create_user(username='other-owner-p', password='Pass-12345!')

        cls.company = Company.objects.create(name='Product Company', owner=cls.owner)
        cls.product = Product.objects.create(
            company=cls.company, name='Main Product', description='Product description',
        )
        cls.member_team = Team.objects.create(
            product=cls.product, name='Visible Team', description='Visible to member',
        )
        cls.hidden_team = Team.objects.create(product=cls.product, name='Hidden Team')
        TeamMember.objects.create(team=cls.member_team, user=cls.member)

        cls.other_product = Product.objects.create(company=cls.company, name='Other Product')
        cls.other_team = Team.objects.create(product=cls.other_product, name='Other Team')
        TeamMember.objects.create(team=cls.other_team, user=cls.other_member)

        cls.private_company = Company.objects.create(name='Private Company', owner=cls.other_owner)

    def test_product_pages_require_authentication(self):
        urls = [
            reverse('tracker:product_create', args=[self.company.pk]),
            reverse('tracker:product_detail', args=[self.product.pk]),
            reverse('tracker:product_edit', args=[self.product.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertRedirects(
                    self.client.get(url),
                    f"{reverse('tracker:login')}?next={url}",
                )

    def test_owner_creates_product_for_url_company_and_posted_company_is_ignored(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('tracker:product_create', args=[self.company.pk]),
            {
                'name': 'Created Product',
                'description': 'Created from form',
                'company': self.private_company.pk,
            },
        )
        product = Product.objects.get(name='Created Product')
        self.assertEqual(product.company, self.company)
        self.assertRedirects(
            response, reverse('tracker:product_detail', args=[product.pk]),
        )

    def test_non_owner_cannot_create_product(self):
        create_url = reverse('tracker:product_create', args=[self.company.pk])
        for user in [self.member, self.outsider]:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertEqual(self.client.get(create_url).status_code, 403)
                self.assertEqual(
                    self.client.post(create_url, {'name': 'Forbidden'}).status_code,
                    403,
                )
        self.assertFalse(Product.objects.filter(name='Forbidden').exists())

    def test_create_rejects_empty_name(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('tracker:product_create', args=[self.company.pk]),
            {'name': '   ', 'description': 'Invalid'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('name', response.context['form'].errors)
        self.assertFalse(Product.objects.filter(description='Invalid').exists())

    def test_owner_sees_all_teams_and_can_edit_without_changing_company(self):
        self.client.force_login(self.owner)
        detail_url = reverse('tracker:product_detail', args=[self.product.pk])
        detail = self.client.get(detail_url)
        self.assertContains(detail, 'Visible Team')
        self.assertContains(detail, 'Hidden Team')
        self.assertContains(detail, 'Редактировать')

        response = self.client.post(
            reverse('tracker:product_edit', args=[self.product.pk]),
            {
                'name': 'Renamed Product',
                'description': 'Updated',
                'company': self.private_company.pk,
            },
        )
        self.assertRedirects(response, detail_url)
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, 'Renamed Product')
        self.assertEqual(self.product.company, self.company)

    def test_team_member_sees_only_own_teams_and_cannot_edit(self):
        self.client.force_login(self.member)
        detail = self.client.get(
            reverse('tracker:product_detail', args=[self.product.pk]),
        )
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, 'Visible Team')
        self.assertNotContains(detail, 'Hidden Team')
        self.assertNotContains(detail, 'Редактировать')

        edit_url = reverse('tracker:product_edit', args=[self.product.pk])
        self.assertEqual(self.client.get(edit_url).status_code, 403)
        self.assertEqual(
            self.client.post(edit_url, {'name': 'Forbidden edit'}).status_code,
            403,
        )

    def test_unrelated_member_and_outsider_get_403_and_missing_product_gets_404(self):
        detail_url = reverse('tracker:product_detail', args=[self.product.pk])
        edit_url = reverse('tracker:product_edit', args=[self.product.pk])
        for user in [self.other_member, self.outsider]:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertEqual(self.client.get(detail_url).status_code, 403)
                self.assertEqual(self.client.get(edit_url).status_code, 403)

        self.client.force_login(self.owner)
        for name in ['tracker:product_detail', 'tracker:product_edit']:
            with self.subTest(name=name):
                self.assertEqual(
                    self.client.get(reverse(name, args=[999999])).status_code,
                    404,
                )

    def test_product_forms_require_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(
            client.post(
                reverse('tracker:product_create', args=[self.company.pk]),
                {'name': 'No CSRF'},
            ).status_code,
            403,
        )
        self.assertEqual(
            client.post(
                reverse('tracker:product_edit', args=[self.product.pk]),
                {'name': 'No CSRF'},
            ).status_code,
            403,
        )

    def test_company_detail_links_products_and_limits_create_button_to_owner(self):
        company_url = reverse('tracker:company_detail', args=[self.company.pk])
        product_url = reverse('tracker:product_detail', args=[self.product.pk])
        create_url = reverse('tracker:product_create', args=[self.company.pk])

        self.client.force_login(self.owner)
        owner_page = self.client.get(company_url)
        self.assertContains(owner_page, f'href="{product_url}"')
        self.assertContains(owner_page, f'href="{create_url}"')

        self.client.force_login(self.member)
        member_page = self.client.get(company_url)
        self.assertContains(member_page, f'href="{product_url}"')
        self.assertNotContains(member_page, f'href="{create_url}"')

