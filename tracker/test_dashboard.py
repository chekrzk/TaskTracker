from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Company, Product, Task, Team, TeamMember


class DashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.user = users.objects.create_user(
            username='dashboard-user',
            first_name='Dashboard',
            password='Pass-12345!',
        )
        cls.other_owner = users.objects.create_user(
            username='dashboard-owner',
            password='Pass-12345!',
        )
        cls.empty_user = users.objects.create_user(
            username='empty-dashboard-user',
            password='Pass-12345!',
        )

        cls.owned_company = Company.objects.create(
            name='Owned Company',
            owner=cls.user,
        )
        cls.owned_product = Product.objects.create(
            company=cls.owned_company,
            name='Owned Product',
        )
        cls.owned_team = Team.objects.create(
            product=cls.owned_product,
            name='Owned Lead Team',
        )
        TeamMember.objects.create(
            team=cls.owned_team,
            user=cls.user,
            role=TeamMember.Role.LEAD,
        )
        cls.owner_only_team = Team.objects.create(
            product=cls.owned_product,
            name='Owner Readonly Team',
        )

        cls.joined_company = Company.objects.create(
            name='Joined Company',
            owner=cls.other_owner,
        )
        cls.joined_product = Product.objects.create(
            company=cls.joined_company,
            name='Joined Product',
        )
        cls.developer_team = Team.objects.create(
            product=cls.joined_product,
            name='Developer Team',
        )
        cls.tester_team = Team.objects.create(
            product=cls.joined_product,
            name='Tester Team',
        )
        cls.member_team = Team.objects.create(
            product=cls.joined_product,
            name='Member Team',
        )
        cls.foreign_team = Team.objects.create(
            product=cls.joined_product,
            name='Foreign Team',
        )
        for team, role in [
            (cls.developer_team, TeamMember.Role.DEVELOPER),
            (cls.tester_team, TeamMember.Role.TESTER),
            (cls.member_team, TeamMember.Role.MEMBER),
        ]:
            TeamMember.objects.create(team=team, user=cls.user, role=role)
        TeamMember.objects.create(
            team=cls.foreign_team,
            user=cls.other_owner,
            role=TeamMember.Role.LEAD,
        )

        cls.assigned_developer = cls.create_task(
            cls.developer_team,
            'Assigned developer task',
            assignee=cls.user,
        )
        cls.assigned_owned = cls.create_task(
            cls.owned_team,
            'Assigned owned task',
            assignee=cls.user,
        )
        cls.tester_task = cls.create_task(
            cls.tester_team,
            'Tester visible task',
        )
        cls.member_task = cls.create_task(
            cls.member_team,
            'Member visible task',
        )
        cls.owner_only_task = cls.create_task(
            cls.owner_only_team,
            'Owner visible task',
        )
        cls.foreign_assigned = cls.create_task(
            cls.foreign_team,
            'Foreign assigned task',
            assignee=cls.user,
        )

    @classmethod
    def create_task(cls, team, title, assignee=None):
        return Task.objects.create(
            team=team,
            column=team.columns.get(position=0),
            title=title,
            author=cls.other_owner,
            assignee=assignee,
        )

    def test_dashboard_requires_authentication(self):
        url = reverse('tracker:home')
        self.assertRedirects(
            self.client.get(url),
            f"{reverse('tracker:login')}?next={url}",
        )

    def test_dashboard_context_contains_only_accessible_data(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('tracker:home'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['companies'], [self.owned_company])
        self.assertCountEqual(
            response.context['teams'],
            [
                self.owned_team,
                self.owner_only_team,
                self.developer_team,
                self.tester_team,
                self.member_team,
            ],
        )
        self.assertEqual(response.context['company_count'], 1)
        self.assertEqual(response.context['team_count'], 5)
        self.assertEqual(response.context['assigned_task_count'], 2)
        self.assertEqual(response.context['accessible_task_count'], 5)
        self.assertEqual(
            response.context['assigned_tasks'],
            [self.assigned_owned, self.assigned_developer],
        )
        self.assertEqual(
            response.context['recent_tasks'],
            [
                self.owner_only_task,
                self.member_task,
                self.tester_task,
                self.assigned_owned,
                self.assigned_developer,
            ],
        )
        self.assertNotIn(
            self.foreign_assigned,
            response.context['assigned_tasks'],
        )
        self.assertNotIn(
            self.foreign_assigned,
            response.context['recent_tasks'],
        )

    def test_dashboard_renders_links_roles_and_role_specific_actions(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('tracker:home'))

        self.assertNotContains(
            response,
            'Разделы приложения будут появляться здесь',
        )
        self.assertContains(response, 'Owned Company')
        self.assertContains(response, 'Owned Lead Team')
        self.assertContains(response, 'Developer Team')
        self.assertContains(response, 'Tester Team')
        self.assertContains(response, 'Member Team')
        self.assertContains(response, 'Owner Readonly Team')
        self.assertContains(response, 'Владелец компании')
        self.assertContains(response, 'Assigned developer task')
        self.assertContains(response, 'Owner visible task')
        self.assertNotContains(response, 'Foreign assigned task')

        for team in [
            self.owned_team,
            self.owner_only_team,
            self.developer_team,
            self.tester_team,
            self.member_team,
        ]:
            self.assertContains(
                response,
                reverse('tracker:team_detail', args=[team.pk]),
            )

        for team in [self.owned_team, self.developer_team]:
            self.assertContains(
                response,
                reverse('tracker:task_create', args=[team.pk]),
            )
        for team in [
            self.owner_only_team,
            self.tester_team,
            self.member_team,
        ]:
            self.assertNotContains(
                response,
                reverse('tracker:task_create', args=[team.pk]),
            )

        self.assertContains(
            response,
            f'href="{reverse("tracker:home")}#my-tasks"',
        )

    def test_dashboard_limits_task_previews_and_keeps_totals(self):
        extra_tasks = [
            self.create_task(
                self.developer_team,
                f'Extra assigned task {index}',
                assignee=self.user,
            )
            for index in range(10)
        ]
        self.client.force_login(self.user)
        response = self.client.get(reverse('tracker:home'))

        self.assertEqual(response.context['assigned_task_count'], 12)
        self.assertEqual(response.context['accessible_task_count'], 15)
        self.assertEqual(len(response.context['assigned_tasks']), 8)
        self.assertEqual(len(response.context['recent_tasks']), 8)
        self.assertEqual(
            response.context['assigned_tasks'],
            list(reversed(extra_tasks[-8:])),
        )
        self.assertEqual(
            response.context['recent_tasks'],
            list(reversed(extra_tasks[-8:])),
        )
        self.assertContains(
            response,
            'Показаны 8 недавно обновлённых задач из 12.',
        )

    def test_empty_dashboard_has_clear_next_steps(self):
        self.client.force_login(self.empty_user)
        response = self.client.get(reverse('tracker:home'))

        self.assertEqual(response.context['company_count'], 0)
        self.assertEqual(response.context['team_count'], 0)
        self.assertEqual(response.context['assigned_task_count'], 0)
        self.assertEqual(response.context['accessible_task_count'], 0)
        self.assertContains(response, 'У вас пока нет компаний.')
        self.assertContains(
            response,
            'Вы пока не состоите ни в одной команде.',
        )
        self.assertContains(
            response,
            'На вас пока не назначены задачи.',
        )
        self.assertContains(
            response,
            'В доступных командах пока нет задач.',
        )
