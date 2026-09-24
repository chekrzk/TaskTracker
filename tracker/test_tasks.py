from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .models import Company, Product, Task, Team, TeamMember


class TaskViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.owner = users.objects.create_user(
            username='task-owner', password='Pass-12345!',
        )
        cls.lead = users.objects.create_user(
            username='task-lead', password='Pass-12345!',
        )
        cls.developer = users.objects.create_user(
            username='task-developer', password='Pass-12345!',
        )
        cls.tester = users.objects.create_user(
            username='task-tester', password='Pass-12345!',
        )
        cls.member = users.objects.create_user(
            username='task-member', password='Pass-12345!',
        )
        cls.outsider = users.objects.create_user(
            username='task-outsider', password='Pass-12345!',
        )
        cls.other_member = users.objects.create_user(
            username='other-team-member', password='Pass-12345!',
        )

        cls.company = Company.objects.create(
            name='Task Company', owner=cls.owner,
        )
        cls.product = Product.objects.create(
            company=cls.company,
            name='Task Product',
        )
        cls.team = Team.objects.create(
            product=cls.product,
            name='Task Team',
        )
        for user, role in [
            (cls.lead, TeamMember.Role.LEAD),
            (cls.developer, TeamMember.Role.DEVELOPER),
            (cls.tester, TeamMember.Role.TESTER),
            (cls.member, TeamMember.Role.MEMBER),
        ]:
            TeamMember.objects.create(team=cls.team, user=user, role=role)

        cls.first_column = cls.team.columns.get(position=0)
        cls.second_column = cls.team.columns.get(position=1)
        cls.task = Task.objects.create(
            team=cls.team,
            title='Existing task',
            description='Task description',
            type=Task.Type.BUG,
            column=cls.first_column,
            priority=Task.Priority.HIGH,
            author=cls.lead,
            assignee=cls.developer,
            due_date=date(2026, 10, 15),
        )

        cls.other_team = Team.objects.create(
            product=cls.product,
            name='Other Task Team',
        )
        TeamMember.objects.create(
            team=cls.other_team,
            user=cls.other_member,
            role=TeamMember.Role.DEVELOPER,
        )
        cls.other_column = cls.other_team.columns.get(position=0)

    def test_task_pages_require_authentication(self):
        urls = [
            reverse('tracker:task_create', args=[self.team.pk]),
            reverse('tracker:task_detail', args=[self.task.pk]),
            reverse('tracker:task_edit', args=[self.task.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertRedirects(
                    self.client.get(url),
                    f"{reverse('tracker:login')}?next={url}",
                )

    def test_lead_creates_task_with_server_fields_and_assignee(self):
        self.client.force_login(self.lead)
        response = self.client.post(
            reverse('tracker:task_create', args=[self.team.pk]),
            {
                'title': 'Lead task',
                'description': 'Created by lead',
                'type': Task.Type.STORY,
                'priority': Task.Priority.CRITICAL,
                'assignee': self.tester.pk,
                'column': self.second_column.pk,
                'due_date': '2026-11-20',
                'team': self.other_team.pk,
                'author': self.outsider.pk,
            },
        )
        task = Task.objects.get(title='Lead task')
        self.assertRedirects(
            response,
            reverse('tracker:task_detail', args=[task.pk]),
        )
        self.assertEqual(task.team, self.team)
        self.assertEqual(task.author, self.lead)
        self.assertEqual(task.column, self.first_column)
        self.assertEqual(task.assignee, self.tester)
        self.assertEqual(task.due_date, date(2026, 11, 20))

    def test_developer_creates_task_but_cannot_assign_user(self):
        self.client.force_login(self.developer)
        response = self.client.post(
            reverse('tracker:task_create', args=[self.team.pk]),
            {
                'title': 'Developer task',
                'description': '',
                'type': Task.Type.TASK,
                'priority': Task.Priority.MEDIUM,
                'assignee': self.developer.pk,
                'due_date': '',
            },
        )
        task = Task.objects.get(title='Developer task')
        self.assertRedirects(
            response,
            reverse('tracker:task_detail', args=[task.pk]),
        )
        self.assertEqual(task.author, self.developer)
        self.assertIsNone(task.assignee)
        self.assertEqual(task.column, self.first_column)

    def test_users_without_create_role_get_403(self):
        create_url = reverse('tracker:task_create', args=[self.team.pk])
        for user in [self.owner, self.tester, self.member, self.outsider]:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertEqual(self.client.get(create_url).status_code, 403)
                self.assertEqual(
                    self.client.post(
                        create_url,
                        {
                            'title': 'Forbidden task',
                            'type': Task.Type.TASK,
                            'priority': Task.Priority.MEDIUM,
                        },
                    ).status_code,
                    403,
                )
        self.assertFalse(Task.objects.filter(title='Forbidden task').exists())

    def test_task_creation_requires_nonempty_board(self):
        empty_team = Team.objects.create(
            product=self.product,
            name='Empty Board Team',
        )
        TeamMember.objects.create(
            team=empty_team,
            user=self.lead,
            role=TeamMember.Role.LEAD,
        )
        empty_team.columns.all().delete()

        self.client.force_login(self.lead)
        create_url = reverse(
            'tracker:task_create',
            args=[empty_team.pk],
        )
        response = self.client.get(create_url)
        self.assertRedirects(
            response,
            reverse('tracker:team_detail', args=[empty_team.pk]),
        )
        messages = list(response.wsgi_request._messages)
        self.assertEqual(
            str(messages[0]),
            'Нельзя создать задачу: сначала добавьте колонку на доску.',
        )

        detail = self.client.get(
            reverse('tracker:team_detail', args=[empty_team.pk]),
        )
        self.assertNotContains(detail, create_url)

    def test_create_validates_title_and_assignee_team(self):
        self.client.force_login(self.lead)
        create_url = reverse('tracker:task_create', args=[self.team.pk])

        empty_title = self.client.post(
            create_url,
            {
                'title': '   ',
                'type': Task.Type.TASK,
                'priority': Task.Priority.MEDIUM,
            },
        )
        self.assertEqual(empty_title.status_code, 200)
        self.assertIn('title', empty_title.context['form'].errors)

        foreign_assignee = self.client.post(
            create_url,
            {
                'title': 'Invalid assignee',
                'type': Task.Type.TASK,
                'priority': Task.Priority.MEDIUM,
                'assignee': self.other_member.pk,
            },
        )
        self.assertEqual(foreign_assignee.status_code, 200)
        self.assertIn('assignee', foreign_assignee.context['form'].errors)
        self.assertFalse(
            Task.objects.filter(title='Invalid assignee').exists(),
        )

    def test_accessible_users_see_task_details(self):
        detail_url = reverse(
            'tracker:task_detail',
            args=[self.task.pk],
        )
        for user in [
            self.owner,
            self.lead,
            self.developer,
            self.tester,
            self.member,
        ]:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(detail_url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'Existing task')
                self.assertContains(response, 'Task description')
                self.assertContains(response, 'TODO')
                self.assertContains(response, 'task-developer')
                self.assertContains(response, '15.10.2026')

    def test_outsider_gets_403_and_missing_task_gets_404(self):
        self.client.force_login(self.outsider)
        self.assertEqual(
            self.client.get(
                reverse('tracker:task_detail', args=[self.task.pk]),
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                reverse('tracker:task_edit', args=[self.task.pk]),
            ).status_code,
            403,
        )

        self.client.force_login(self.owner)
        for name in ['tracker:task_detail', 'tracker:task_edit']:
            with self.subTest(name=name):
                self.assertEqual(
                    self.client.get(
                        reverse(name, args=[999999]),
                    ).status_code,
                    404,
                )
        self.assertEqual(
            self.client.get(
                reverse('tracker:task_create', args=[999999]),
            ).status_code,
            404,
        )

    def test_lead_edits_task_and_preserves_team_and_author(self):
        self.client.force_login(self.lead)
        response = self.client.post(
            reverse('tracker:task_edit', args=[self.task.pk]),
            {
                'title': 'Updated task',
                'description': 'Updated description',
                'type': Task.Type.STORY,
                'priority': Task.Priority.CRITICAL,
                'assignee': self.tester.pk,
                'column': self.second_column.pk,
                'due_date': '2026-12-01',
                'team': self.other_team.pk,
                'author': self.outsider.pk,
            },
        )
        self.assertRedirects(
            response,
            reverse('tracker:task_detail', args=[self.task.pk]),
        )
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, 'Updated task')
        self.assertEqual(self.task.team, self.team)
        self.assertEqual(self.task.author, self.lead)
        self.assertEqual(self.task.assignee, self.tester)
        self.assertEqual(self.task.column, self.second_column)
        self.assertEqual(self.task.due_date, date(2026, 12, 1))

    def test_only_lead_can_edit_task(self):
        edit_url = reverse('tracker:task_edit', args=[self.task.pk])
        for user in [
            self.owner,
            self.developer,
            self.tester,
            self.member,
            self.outsider,
        ]:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertEqual(self.client.get(edit_url).status_code, 403)
                self.assertEqual(
                    self.client.post(
                        edit_url,
                        {
                            'title': 'Forbidden edit',
                            'type': Task.Type.TASK,
                            'priority': Task.Priority.LOW,
                            'column': self.first_column.pk,
                        },
                    ).status_code,
                    403,
                )

    def test_edit_rejects_foreign_column_and_assignee(self):
        self.client.force_login(self.lead)
        edit_url = reverse('tracker:task_edit', args=[self.task.pk])
        response = self.client.post(
            edit_url,
            {
                'title': 'Invalid relations',
                'type': Task.Type.TASK,
                'priority': Task.Priority.MEDIUM,
                'assignee': self.other_member.pk,
                'column': self.other_column.pk,
                'due_date': '',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('assignee', response.context['form'].errors)
        self.assertIn('column', response.context['form'].errors)
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, 'Existing task')
        self.assertEqual(self.task.column, self.first_column)
        self.assertEqual(self.task.assignee, self.developer)

    def test_team_board_links_tasks_and_limits_create_button_by_role(self):
        team_url = reverse('tracker:team_detail', args=[self.team.pk])
        task_url = reverse('tracker:task_detail', args=[self.task.pk])
        create_url = reverse('tracker:task_create', args=[self.team.pk])

        for user in [self.lead, self.developer]:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(team_url)
                self.assertContains(response, f'href="{task_url}"')
                self.assertContains(response, f'href="{create_url}"')

        for user in [self.owner, self.tester, self.member]:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(team_url)
                self.assertContains(response, f'href="{task_url}"')
                self.assertNotContains(response, f'href="{create_url}"')

    def test_task_forms_require_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.lead)
        self.assertEqual(
            client.post(
                reverse('tracker:task_create', args=[self.team.pk]),
                {
                    'title': 'No CSRF',
                    'type': Task.Type.TASK,
                    'priority': Task.Priority.MEDIUM,
                },
            ).status_code,
            403,
        )
        self.assertEqual(
            client.post(
                reverse('tracker:task_edit', args=[self.task.pk]),
                {
                    'title': 'No CSRF',
                    'type': Task.Type.TASK,
                    'priority': Task.Priority.MEDIUM,
                    'column': self.first_column.pk,
                },
            ).status_code,
            403,
        )
