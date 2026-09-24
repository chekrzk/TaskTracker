import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .models import Company, Product, Task, Team, TeamMember


class TaskColumnUpdateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.owner = users.objects.create_user(
            username='drag-owner', password='Pass-12345!',
        )
        cls.lead = users.objects.create_user(
            username='drag-lead', password='Pass-12345!',
        )
        cls.developer = users.objects.create_user(
            username='drag-developer', password='Pass-12345!',
        )
        cls.tester = users.objects.create_user(
            username='drag-tester', password='Pass-12345!',
        )
        cls.member = users.objects.create_user(
            username='drag-member', password='Pass-12345!',
        )
        cls.outsider = users.objects.create_user(
            username='drag-outsider', password='Pass-12345!',
        )

        cls.company = Company.objects.create(
            name='Drag Company', owner=cls.owner,
        )
        cls.product = Product.objects.create(
            company=cls.company,
            name='Drag Product',
        )
        cls.team = Team.objects.create(
            product=cls.product,
            name='Drag Team',
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
            title='Draggable task',
            column=cls.first_column,
            author=cls.lead,
        )

        cls.other_team = Team.objects.create(
            product=cls.product,
            name='Other Drag Team',
        )
        cls.other_column = cls.other_team.columns.get(position=0)

    def post_column(self, user, column_id):
        self.client.force_login(user)
        return self.client.post(
            reverse(
                'tracker:task_column_update',
                args=[self.task.pk],
            ),
            data=json.dumps({'column_id': column_id}),
            content_type='application/json',
        )

    def test_endpoint_requires_authentication(self):
        url = reverse(
            'tracker:task_column_update',
            args=[self.task.pk],
        )
        response = self.client.post(
            url,
            data=json.dumps({'column_id': self.second_column.pk}),
            content_type='application/json',
        )
        self.assertRedirects(
            response,
            f"{reverse('tracker:login')}?next={url}",
        )

    def test_lead_developer_and_tester_can_move_task(self):
        for user in [self.lead, self.developer, self.tester]:
            with self.subTest(user=user.username):
                Task.objects.filter(pk=self.task.pk).update(
                    column=self.first_column,
                )
                response = self.post_column(
                    user,
                    self.second_column.pk,
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {
                    'success': True,
                    'column_id': self.second_column.pk,
                })
                self.task.refresh_from_db()
                self.assertEqual(
                    self.task.column,
                    self.second_column,
                )

    def test_owner_member_and_outsider_cannot_move_task(self):
        for user in [self.owner, self.member, self.outsider]:
            with self.subTest(user=user.username):
                response = self.post_column(
                    user,
                    self.second_column.pk,
                )
                self.assertEqual(response.status_code, 403)
                self.assertFalse(response.json()['success'])
                self.task.refresh_from_db()
                self.assertEqual(self.task.column, self.first_column)

    def test_foreign_and_missing_columns_are_rejected(self):
        for column_id in [self.other_column.pk, 999999]:
            with self.subTest(column_id=column_id):
                response = self.post_column(self.lead, column_id)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()['success'], False)
                self.assertIn('Колонка не найдена', response.json()['error'])
                self.task.refresh_from_db()
                self.assertEqual(self.task.column, self.first_column)

    def test_invalid_json_and_column_id_are_rejected(self):
        self.client.force_login(self.lead)
        url = reverse(
            'tracker:task_column_update',
            args=[self.task.pk],
        )
        invalid_payloads = [
            '{invalid',
            json.dumps({}),
            json.dumps({'column_id': str(self.second_column.pk)}),
            json.dumps({'column_id': True}),
            json.dumps([]),
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                response = self.client.post(
                    url,
                    data=payload,
                    content_type='application/json',
                )
                self.assertEqual(response.status_code, 400)
                self.assertFalse(response.json()['success'])
                self.task.refresh_from_db()
                self.assertEqual(self.task.column, self.first_column)

    def test_missing_task_returns_404_and_get_is_not_allowed(self):
        self.client.force_login(self.lead)
        missing = self.client.post(
            reverse('tracker:task_column_update', args=[999999]),
            data=json.dumps({'column_id': self.second_column.pk}),
            content_type='application/json',
        )
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(
            self.client.get(
                reverse(
                    'tracker:task_column_update',
                    args=[self.task.pk],
                ),
            ).status_code,
            405,
        )

    def test_endpoint_is_csrf_protected(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.lead)
        response = client.post(
            reverse(
                'tracker:task_column_update',
                args=[self.task.pk],
            ),
            data=json.dumps({'column_id': self.second_column.pk}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        self.task.refresh_from_db()
        self.assertEqual(self.task.column, self.first_column)

    def test_drag_interface_is_available_only_to_allowed_roles(self):
        detail_url = reverse(
            'tracker:team_detail',
            args=[self.team.pk],
        )
        move_url = reverse(
            'tracker:task_column_update',
            args=[self.task.pk],
        )

        for user in [self.lead, self.developer, self.tester]:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(detail_url)
                self.assertContains(
                    response,
                    'data-can-move-tasks="true"',
                )
                self.assertContains(
                    response,
                    f'data-move-url="{move_url}"',
                )
                self.assertContains(
                    response,
                    'sortablejs@1.15.7/Sortable.min.js',
                )
                self.assertContains(
                    response,
                    'tracker/js/board.js',
                )
                self.assertContains(
                    response,
                    'sha384-DgmC6Xe2bSN2WjTDXzWYbUbxyhNP+NNkGDR/g78pCXV7E7rcVTGxVg0uIVCUUcBc',
                )

        for user in [self.owner, self.member]:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(detail_url)
                self.assertContains(
                    response,
                    'data-can-move-tasks="false"',
                )
                self.assertNotContains(
                    response,
                    'sortablejs@1.15.7/Sortable.min.js',
                )
                self.assertNotContains(
                    response,
                    'tracker/js/board.js',
                )
