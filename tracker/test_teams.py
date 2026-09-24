from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .models import Company, Product, Task, Team, TeamMember


class TeamViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.owner = users.objects.create_user(
            username='team-owner', password='Pass-12345!',
        )
        cls.lead = users.objects.create_user(
            username='team-lead', password='Pass-12345!',
        )
        cls.member = users.objects.create_user(
            username='team-member', password='Pass-12345!',
        )
        cls.candidate = users.objects.create_user(
            username='team-candidate', password='Pass-12345!',
        )
        cls.outsider = users.objects.create_user(
            username='team-outsider', password='Pass-12345!',
        )
        cls.other_owner = users.objects.create_user(
            username='other-team-owner', password='Pass-12345!',
        )

        cls.company = Company.objects.create(
            name='Team Company', owner=cls.owner,
        )
        cls.product = Product.objects.create(
            company=cls.company,
            name='Team Product',
            description='Product with teams',
        )
        cls.team = Team.objects.create(
            product=cls.product,
            name='Backend Team',
            description='Main team',
        )
        cls.lead_membership = TeamMember.objects.create(
            team=cls.team,
            user=cls.lead,
            role=TeamMember.Role.LEAD,
        )
        cls.member_membership = TeamMember.objects.create(
            team=cls.team,
            user=cls.member,
            role=TeamMember.Role.DEVELOPER,
        )
        cls.task = Task.objects.create(
            team=cls.team,
            column=cls.team.columns.get(position=0),
            title='Visible task',
            author=cls.lead,
        )

        cls.other_product = Product.objects.create(
            company=cls.company,
            name='Other Team Product',
        )
        cls.other_team = Team.objects.create(
            product=cls.other_product,
            name='Other Product Team',
        )

        cls.private_company = Company.objects.create(
            name='Private Team Company',
            owner=cls.other_owner,
        )
        cls.private_product = Product.objects.create(
            company=cls.private_company,
            name='Private Team Product',
        )
        cls.private_team = Team.objects.create(
            product=cls.private_product,
            name='Private Team',
        )

    def test_team_pages_require_authentication(self):
        urls = [
            reverse('tracker:team_list'),
            reverse('tracker:team_create', args=[self.product.pk]),
            reverse('tracker:team_detail', args=[self.team.pk]),
            reverse('tracker:team_edit', args=[self.team.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertRedirects(
                    self.client.get(url),
                    f"{reverse('tracker:login')}?next={url}",
                )

    def test_team_list_contains_owned_and_joined_teams_only(self):
        cases = [
            (
                self.owner,
                ['Backend Team', 'Other Product Team'],
                ['Private Team'],
            ),
            (
                self.lead,
                ['Backend Team'],
                ['Other Product Team', 'Private Team'],
            ),
            (
                self.outsider,
                [],
                ['Backend Team', 'Other Product Team', 'Private Team'],
            ),
        ]
        for user, visible, hidden in cases:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(reverse('tracker:team_list'))
                self.assertEqual(response.status_code, 200)
                for name in visible:
                    self.assertContains(response, name)
                for name in hidden:
                    self.assertNotContains(response, name)

    def test_owner_creates_team_for_url_product_with_default_columns(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('tracker:team_create', args=[self.product.pk]),
            {
                'name': 'Created Team',
                'description': 'Created from form',
                'product': self.private_product.pk,
            },
        )
        team = Team.objects.get(name='Created Team')
        self.assertEqual(team.product, self.product)
        self.assertRedirects(
            response,
            reverse('tracker:team_detail', args=[team.pk]),
        )
        self.assertEqual(
            list(team.columns.values_list('name', 'position')),
            [
                ('TODO', 0),
                ('IN PROGRESS', 1),
                ('REVIEW', 2),
                ('TESTING', 3),
                ('DONE', 4),
            ],
        )
        self.assertTrue(
            TeamMember.objects.filter(
                team=team,
                user=self.owner,
                role=TeamMember.Role.LEAD,
            ).exists(),
        )

    def test_non_owner_cannot_create_team(self):
        create_url = reverse('tracker:team_create', args=[self.product.pk])
        for user in [self.lead, self.member, self.outsider]:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertEqual(self.client.get(create_url).status_code, 403)
                self.assertEqual(
                    self.client.post(
                        create_url, {'name': 'Forbidden Team'},
                    ).status_code,
                    403,
                )
        self.assertFalse(Team.objects.filter(name='Forbidden Team').exists())

    def test_create_rejects_empty_name_and_missing_product_is_404(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('tracker:team_create', args=[self.product.pk]),
            {'name': '   ', 'description': 'Invalid'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('name', response.context['form'].errors)
        self.assertFalse(Team.objects.filter(description='Invalid').exists())
        self.assertEqual(
            self.client.get(
                reverse('tracker:team_create', args=[999999]),
            ).status_code,
            404,
        )

    def test_product_detail_links_teams_and_limits_create_button_to_owner(self):
        product_url = reverse('tracker:product_detail', args=[self.product.pk])
        team_url = reverse('tracker:team_detail', args=[self.team.pk])
        create_url = reverse('tracker:team_create', args=[self.product.pk])

        self.client.force_login(self.owner)
        owner_page = self.client.get(product_url)
        self.assertContains(owner_page, f'href="{team_url}"')
        self.assertContains(owner_page, f'href="{create_url}"')

        self.client.force_login(self.member)
        member_page = self.client.get(product_url)
        self.assertContains(member_page, f'href="{team_url}"')
        self.assertNotContains(member_page, f'href="{create_url}"')

    def test_team_detail_shows_members_columns_and_tasks(self):
        for user in [self.owner, self.lead, self.member]:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(
                    reverse('tracker:team_detail', args=[self.team.pk]),
                )
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'team-lead')
                self.assertContains(response, 'team-member')
                self.assertContains(response, 'TODO')
                self.assertContains(response, 'IN PROGRESS')
                self.assertContains(response, 'Visible task')

        self.client.force_login(self.member)
        member_page = self.client.get(
            reverse('tracker:team_detail', args=[self.team.pk]),
        )
        self.assertNotContains(member_page, 'Добавить участника')
        self.assertNotContains(member_page, 'Редактировать')
        self.assertNotContains(member_page, 'Удалить')

    def test_outsider_cannot_view_or_manage_team(self):
        self.client.force_login(self.outsider)
        urls = [
            reverse('tracker:team_detail', args=[self.team.pk]),
            reverse('tracker:team_edit', args=[self.team.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(
            self.client.get(
                reverse('tracker:team_detail', args=[999999]),
            ).status_code,
            404,
        )

    def test_only_lead_can_edit_team_and_product_cannot_be_changed(self):
        edit_url = reverse('tracker:team_edit', args=[self.team.pk])
        self.client.force_login(self.lead)
        response = self.client.post(
            edit_url,
            {
                'name': 'Lead renamed team',
                'description': 'Updated',
                'product': self.private_product.pk,
            },
        )
        self.assertRedirects(
            response,
            reverse('tracker:team_detail', args=[self.team.pk]),
        )
        self.team.refresh_from_db()
        self.assertEqual(self.team.name, 'Lead renamed team')
        self.assertEqual(self.team.product, self.product)

        for user in [self.owner, self.member]:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertEqual(self.client.get(edit_url).status_code, 403)
                self.assertEqual(
                    self.client.post(edit_url, {'name': 'Forbidden'}).status_code,
                    403,
                )

    def test_only_lead_can_add_members_with_role(self):
        add_url = reverse('tracker:team_member_add', args=[self.team.pk])
        self.client.force_login(self.lead)
        response = self.client.post(
            add_url,
            {'user': self.candidate.pk, 'role': TeamMember.Role.TESTER},
        )
        self.assertRedirects(
            response,
            reverse('tracker:team_detail', args=[self.team.pk]),
        )
        membership = TeamMember.objects.get(
            team=self.team,
            user=self.candidate,
        )
        self.assertEqual(membership.role, TeamMember.Role.TESTER)

        membership.delete()
        self.client.force_login(self.owner)
        self.assertEqual(
            self.client.post(
                add_url,
                {'user': self.candidate.pk, 'role': TeamMember.Role.LEAD},
            ).status_code,
            403,
        )
        self.assertFalse(
            TeamMember.objects.filter(
                team=self.team,
                user=self.candidate,
            ).exists(),
        )

    def test_duplicate_member_is_rejected(self):
        self.client.force_login(self.lead)
        response = self.client.post(
            reverse('tracker:team_member_add', args=[self.team.pk]),
            {'user': self.member.pk, 'role': TeamMember.Role.TESTER},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Пользователь уже состоит в этой команде.',
        )
        self.assertEqual(
            TeamMember.objects.filter(
                team=self.team,
                user=self.member,
            ).count(),
            1,
        )

    def test_non_manager_cannot_add_or_delete_members(self):
        add_url = reverse('tracker:team_member_add', args=[self.team.pk])
        delete_url = reverse(
            'tracker:team_member_delete',
            args=[self.team.pk, self.lead_membership.pk],
        )
        for user in [self.owner, self.member, self.outsider]:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertEqual(
                    self.client.post(
                        add_url,
                        {
                            'user': self.candidate.pk,
                            'role': TeamMember.Role.MEMBER,
                        },
                    ).status_code,
                    403,
                )
                self.assertEqual(
                    self.client.post(delete_url).status_code,
                    403,
                )

    def test_lead_can_delete_member_and_membership_is_scoped_to_team(self):
        self.client.force_login(self.lead)
        delete_url = reverse(
            'tracker:team_member_delete',
            args=[self.team.pk, self.member_membership.pk],
        )
        self.assertRedirects(
            self.client.post(delete_url),
            reverse('tracker:team_detail', args=[self.team.pk]),
        )
        self.assertFalse(
            TeamMember.objects.filter(pk=self.member_membership.pk).exists(),
        )

        private_membership = TeamMember.objects.create(
            team=self.private_team,
            user=self.candidate,
        )
        self.assertEqual(
            self.client.post(
                reverse(
                    'tracker:team_member_delete',
                    args=[self.team.pk, private_membership.pk],
                ),
            ).status_code,
            404,
        )

    def test_member_mutations_are_post_only_and_csrf_protected(self):
        self.client.force_login(self.lead)
        add_url = reverse('tracker:team_member_add', args=[self.team.pk])
        delete_url = reverse(
            'tracker:team_member_delete',
            args=[self.team.pk, self.member_membership.pk],
        )
        self.assertEqual(self.client.get(add_url).status_code, 405)
        self.assertEqual(self.client.get(delete_url).status_code, 405)

        client = Client(enforce_csrf_checks=True)
        client.force_login(self.lead)
        self.assertEqual(
            client.post(
                add_url,
                {
                    'user': self.candidate.pk,
                    'role': TeamMember.Role.MEMBER,
                },
            ).status_code,
            403,
        )
        self.assertEqual(client.post(delete_url).status_code, 403)

    def test_team_forms_require_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(
            client.post(
                reverse('tracker:team_create', args=[self.product.pk]),
                {'name': 'No CSRF'},
            ).status_code,
            403,
        )
        client.force_login(self.lead)
        self.assertEqual(
            client.post(
                reverse('tracker:team_edit', args=[self.team.pk]),
                {'name': 'No CSRF'},
            ).status_code,
            403,
        )
