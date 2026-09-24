from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Company, Product, Task, Team, TeamMember
from .permissions import (
    can_assign_task,
    can_comment_task,
    can_create_product,
    can_create_task,
    can_create_team,
    can_edit_company,
    can_edit_product,
    can_edit_task,
    can_manage_columns,
    can_manage_members,
    can_manage_team,
    can_move_task,
    can_view_company,
    can_view_product,
    can_view_team,
)


class RolePermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.owner = users.objects.create_user(
            username='permission-owner', password='Pass-12345!',
        )
        cls.lead = users.objects.create_user(
            username='permission-lead', password='Pass-12345!',
        )
        cls.developer = users.objects.create_user(
            username='permission-developer', password='Pass-12345!',
        )
        cls.tester = users.objects.create_user(
            username='permission-tester', password='Pass-12345!',
        )
        cls.member = users.objects.create_user(
            username='permission-member', password='Pass-12345!',
        )
        cls.outsider = users.objects.create_user(
            username='permission-outsider', password='Pass-12345!',
        )
        cls.company = Company.objects.create(
            name='Permission Company',
            owner=cls.owner,
        )
        cls.product = Product.objects.create(
            company=cls.company,
            name='Permission Product',
        )
        cls.team = Team.objects.create(
            product=cls.product,
            name='Permission Team',
        )
        for user, role in [
            (cls.lead, TeamMember.Role.LEAD),
            (cls.developer, TeamMember.Role.DEVELOPER),
            (cls.tester, TeamMember.Role.TESTER),
            (cls.member, TeamMember.Role.MEMBER),
        ]:
            TeamMember.objects.create(team=cls.team, user=user, role=role)
        cls.task = Task.objects.create(
            team=cls.team,
            title='Permission task',
            column=cls.team.columns.get(position=0),
            author=cls.lead,
        )

    def test_company_permissions_are_owner_scoped(self):
        for permission in [
            can_edit_company,
            can_create_product,
        ]:
            with self.subTest(permission=permission.__name__):
                self.assertTrue(permission(self.owner, self.company))
                self.assertFalse(permission(self.lead, self.company))
                self.assertFalse(permission(self.outsider, self.company))

        for permission in [
            can_edit_product,
            can_create_team,
        ]:
            with self.subTest(permission=permission.__name__):
                self.assertTrue(permission(self.owner, self.product))
                self.assertFalse(permission(self.lead, self.product))
                self.assertFalse(permission(self.outsider, self.product))

        self.assertTrue(can_view_company(self.owner, self.company))
        self.assertTrue(can_view_company(self.developer, self.company))
        self.assertFalse(can_view_company(self.outsider, self.company))
        self.assertTrue(can_view_product(self.owner, self.product))
        self.assertTrue(can_view_product(self.tester, self.product))
        self.assertFalse(can_view_product(self.outsider, self.product))

    def test_team_capability_matrix(self):
        permissions = [
            can_manage_team,
            can_manage_members,
            can_manage_columns,
            can_create_task,
            can_edit_task,
            can_assign_task,
            can_move_task,
            can_comment_task,
        ]
        expected = {
            self.lead: [True, True, True, True, True, True, True, True],
            self.developer: [False, False, False, True, False, False, True, True],
            self.tester: [False, False, False, False, False, False, True, True],
            self.member: [False, False, False, False, False, False, False, False],
            self.owner: [False, False, False, False, False, False, False, False],
            self.outsider: [False, False, False, False, False, False, False, False],
        }
        for user, results in expected.items():
            for permission, result in zip(permissions, results, strict=True):
                with self.subTest(
                    user=user.username,
                    permission=permission.__name__,
                ):
                    self.assertEqual(permission(user, self.team), result)

    def test_team_access_is_scoped_to_membership(self):
        for user in [
            self.owner,
            self.lead,
            self.developer,
            self.tester,
            self.member,
        ]:
            with self.subTest(user=user.username):
                self.assertTrue(can_view_team(user, self.team))
        self.assertFalse(can_view_team(self.outsider, self.team))

        second_team = Team.objects.create(
            product=self.product,
            name='Second Permission Team',
        )
        TeamMember.objects.create(
            team=second_team,
            user=self.lead,
            role=TeamMember.Role.MEMBER,
        )
        self.assertTrue(can_manage_team(self.lead, self.team))
        self.assertFalse(can_manage_team(self.lead, second_team))

    def test_server_and_interface_apply_the_same_roles(self):
        team_url = reverse('tracker:team_detail', args=[self.team.pk])
        edit_team_url = reverse('tracker:team_edit', args=[self.team.pk])
        create_task_url = reverse(
            'tracker:task_create',
            args=[self.team.pk],
        )
        edit_task_url = reverse('tracker:task_edit', args=[self.task.pk])

        self.client.force_login(self.lead)
        lead_page = self.client.get(team_url)
        self.assertContains(lead_page, f'href="{edit_team_url}"')
        self.assertContains(lead_page, f'href="{create_task_url}"')
        self.assertEqual(self.client.get(edit_team_url).status_code, 200)
        self.assertEqual(self.client.get(edit_task_url).status_code, 200)

        self.client.force_login(self.developer)
        developer_page = self.client.get(team_url)
        self.assertNotContains(developer_page, f'href="{edit_team_url}"')
        self.assertContains(developer_page, f'href="{create_task_url}"')
        self.assertEqual(self.client.get(edit_team_url).status_code, 403)
        self.assertEqual(self.client.get(edit_task_url).status_code, 403)

        for user in [self.tester, self.member, self.owner]:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                page = self.client.get(team_url)
                self.assertEqual(page.status_code, 200)
                self.assertNotContains(page, f'href="{edit_team_url}"')
                self.assertNotContains(page, f'href="{create_task_url}"')
                self.assertEqual(self.client.get(edit_team_url).status_code, 403)
                self.assertEqual(self.client.get(create_task_url).status_code, 403)
                self.assertEqual(self.client.get(edit_task_url).status_code, 403)

        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(team_url).status_code, 403)
