from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .models import BoardColumn, Company, Product, Task, Team, TeamMember


class BoardColumnViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.owner = users.objects.create_user(
            username='board-owner', password='Pass-12345!',
        )
        cls.lead = users.objects.create_user(
            username='board-lead', password='Pass-12345!',
        )
        cls.developer = users.objects.create_user(
            username='board-developer', password='Pass-12345!',
        )
        cls.outsider = users.objects.create_user(
            username='board-outsider', password='Pass-12345!',
        )

        cls.company = Company.objects.create(
            name='Board Company', owner=cls.owner,
        )
        cls.product = Product.objects.create(
            company=cls.company,
            name='Board Product',
        )
        cls.team = Team.objects.create(
            product=cls.product,
            name='Board Team',
        )
        TeamMember.objects.create(
            team=cls.team,
            user=cls.lead,
            role=TeamMember.Role.LEAD,
        )
        TeamMember.objects.create(
            team=cls.team,
            user=cls.developer,
            role=TeamMember.Role.DEVELOPER,
        )
        cls.columns = list(
            cls.team.columns.order_by('position', 'pk'),
        )
        cls.task = Task.objects.create(
            team=cls.team,
            title='Board task',
            column=cls.columns[0],
            priority=Task.Priority.HIGH,
            author=cls.lead,
            assignee=cls.developer,
        )

        cls.other_team = Team.objects.create(
            product=cls.product,
            name='Other Board Team',
        )
        cls.other_column = cls.other_team.columns.get(position=0)

    def test_column_endpoints_require_authentication(self):
        urls = [
            reverse('tracker:board_column_create', args=[self.team.pk]),
            reverse('tracker:board_columns_reorder', args=[self.team.pk]),
            reverse('tracker:board_column_edit', args=[self.columns[1].pk]),
            reverse('tracker:board_column_delete', args=[self.columns[1].pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.post(url)
                self.assertRedirects(
                    response,
                    f"{reverse('tracker:login')}?next={url}",
                )

    def test_only_lead_sees_column_controls(self):
        detail_url = reverse('tracker:team_detail', args=[self.team.pk])
        create_url = reverse(
            'tracker:board_column_create',
            args=[self.team.pk],
        )
        reorder_url = reverse(
            'tracker:board_columns_reorder',
            args=[self.team.pk],
        )

        self.client.force_login(self.lead)
        lead_page = self.client.get(detail_url)
        self.assertContains(lead_page, f'action="{create_url}"')
        self.assertContains(lead_page, f'action="{reorder_url}"')
        self.assertContains(lead_page, 'Сохранить порядок')
        self.assertContains(lead_page, 'js-column-left')

        for user in [self.owner, self.developer]:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(detail_url)
                self.assertNotContains(response, f'action="{create_url}"')
                self.assertNotContains(response, f'action="{reorder_url}"')
                self.assertNotContains(response, 'Удалить колонку')

    def test_lead_creates_column_at_end(self):
        self.client.force_login(self.lead)
        response = self.client.post(
            reverse('tracker:board_column_create', args=[self.team.pk]),
            {'name': 'READY FOR RELEASE', 'team': self.other_team.pk},
        )
        column = BoardColumn.objects.get(name='READY FOR RELEASE')
        self.assertRedirects(
            response,
            reverse('tracker:team_detail', args=[self.team.pk]),
        )
        self.assertEqual(column.team, self.team)
        self.assertEqual(column.position, 5)

    def test_blank_column_name_is_rejected(self):
        self.client.force_login(self.lead)
        response = self.client.post(
            reverse('tracker:board_column_create', args=[self.team.pk]),
            {'name': '   '},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('name', response.context['column_form'].errors)
        self.assertEqual(self.team.columns.count(), 5)

    def test_non_leads_cannot_mutate_columns(self):
        create_url = reverse(
            'tracker:board_column_create',
            args=[self.team.pk],
        )
        reorder_url = reverse(
            'tracker:board_columns_reorder',
            args=[self.team.pk],
        )
        edit_url = reverse(
            'tracker:board_column_edit',
            args=[self.columns[1].pk],
        )
        delete_url = reverse(
            'tracker:board_column_delete',
            args=[self.columns[1].pk],
        )
        for user in [self.owner, self.developer, self.outsider]:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertEqual(
                    self.client.post(
                        create_url, {'name': 'Forbidden'},
                    ).status_code,
                    403,
                )
                self.assertEqual(
                    self.client.post(
                        reorder_url,
                        {'column_ids': [column.pk for column in self.columns]},
                    ).status_code,
                    403,
                )
                self.assertEqual(
                    self.client.post(
                        edit_url, {'name': 'Forbidden'},
                    ).status_code,
                    403,
                )
                self.assertEqual(
                    self.client.post(delete_url).status_code,
                    403,
                )

    def test_lead_renames_column_without_changing_tasks_or_position(self):
        column = self.columns[0]
        old_position = column.position
        self.client.force_login(self.lead)
        response = self.client.post(
            reverse('tracker:board_column_edit', args=[column.pk]),
            {'name': 'BACKLOG', 'team': self.other_team.pk, 'position': 99},
        )
        self.assertRedirects(
            response,
            reverse('tracker:team_detail', args=[self.team.pk]),
        )
        column.refresh_from_db()
        self.task.refresh_from_db()
        self.assertEqual(column.name, 'BACKLOG')
        self.assertEqual(column.team, self.team)
        self.assertEqual(column.position, old_position)
        self.assertEqual(self.task.column, column)

    def test_blank_edit_renders_error_on_team_page(self):
        column = self.columns[1]
        self.client.force_login(self.lead)
        response = self.client.post(
            reverse('tracker:board_column_edit', args=[column.pk]),
            {'name': '   '},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['editing_column_id'], column.pk)
        self.assertIn('name', response.context['column_edit_form'].errors)
        column.refresh_from_db()
        self.assertEqual(column.name, 'IN PROGRESS')

    def test_reorder_saves_positions_zero_to_n_minus_one(self):
        submitted = [column.pk for column in reversed(self.columns)]
        self.client.force_login(self.lead)
        response = self.client.post(
            reverse('tracker:board_columns_reorder', args=[self.team.pk]),
            {'column_ids': submitted},
        )
        self.assertRedirects(
            response,
            reverse('tracker:team_detail', args=[self.team.pk]),
        )
        actual = list(
            self.team.columns.order_by('position', 'pk').values_list(
                'pk', 'position',
            ),
        )
        self.assertEqual(
            actual,
            [(column_id, position) for position, column_id in enumerate(submitted)],
        )

    def test_reorder_rejects_missing_duplicate_foreign_and_noninteger_ids(self):
        original = [column.pk for column in self.columns]
        invalid_orders = [
            original[:-1],
            original[:-1] + [original[0]],
            original[:-1] + [self.other_column.pk],
            original[:-1] + ['not-an-id'],
        ]
        self.client.force_login(self.lead)
        url = reverse(
            'tracker:board_columns_reorder',
            args=[self.team.pk],
        )
        for submitted in invalid_orders:
            with self.subTest(submitted=submitted):
                response = self.client.post(
                    url,
                    {'column_ids': submitted},
                    follow=True,
                )
                self.assertContains(
                    response,
                    'Передан некорректный порядок колонок.',
                )
                actual = list(
                    self.team.columns.order_by('position', 'pk').values_list(
                        'pk', flat=True,
                    ),
                )
                self.assertEqual(actual, original)

    def test_delete_empty_column_and_block_column_with_tasks(self):
        empty_column = self.columns[1]
        self.client.force_login(self.lead)
        response = self.client.post(
            reverse(
                'tracker:board_column_delete',
                args=[empty_column.pk],
            ),
        )
        self.assertRedirects(
            response,
            reverse('tracker:team_detail', args=[self.team.pk]),
        )
        self.assertFalse(
            BoardColumn.objects.filter(pk=empty_column.pk).exists(),
        )

        occupied = self.columns[0]
        response = self.client.post(
            reverse('tracker:board_column_delete', args=[occupied.pk]),
            follow=True,
        )
        self.assertContains(
            response,
            'Сначала перенесите задачи в другую колонку.',
        )
        self.assertTrue(
            BoardColumn.objects.filter(pk=occupied.pk).exists(),
        )
        self.task.refresh_from_db()
        self.assertEqual(self.task.column_id, occupied.pk)

    def test_column_mutations_are_post_only(self):
        self.client.force_login(self.lead)
        urls = [
            reverse('tracker:board_column_create', args=[self.team.pk]),
            reverse('tracker:board_columns_reorder', args=[self.team.pk]),
            reverse('tracker:board_column_edit', args=[self.columns[1].pk]),
            reverse('tracker:board_column_delete', args=[self.columns[1].pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405)

    def test_column_mutations_are_csrf_protected(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.lead)
        cases = [
            (
                reverse(
                    'tracker:board_column_create',
                    args=[self.team.pk],
                ),
                {'name': 'No CSRF'},
            ),
            (
                reverse(
                    'tracker:board_columns_reorder',
                    args=[self.team.pk],
                ),
                {'column_ids': [column.pk for column in self.columns]},
            ),
            (
                reverse(
                    'tracker:board_column_edit',
                    args=[self.columns[1].pk],
                ),
                {'name': 'No CSRF'},
            ),
            (
                reverse(
                    'tracker:board_column_delete',
                    args=[self.columns[1].pk],
                ),
                {},
            ),
        ]
        for url, data in cases:
            with self.subTest(url=url):
                self.assertEqual(
                    client.post(url, data).status_code,
                    403,
                )

    def test_empty_board_shows_create_form_and_disables_task_creation(self):
        empty_team = Team.objects.create(
            product=self.product,
            name='Empty Managed Board',
        )
        TeamMember.objects.create(
            team=empty_team,
            user=self.lead,
            role=TeamMember.Role.LEAD,
        )
        empty_team.columns.all().delete()

        self.client.force_login(self.lead)
        response = self.client.get(
            reverse('tracker:team_detail', args=[empty_team.pk]),
        )
        self.assertContains(
            response,
            reverse(
                'tracker:board_column_create',
                args=[empty_team.pk],
            ),
        )
        self.assertContains(response, 'Добавьте первую колонку')
        self.assertNotContains(
            response,
            reverse('tracker:task_create', args=[empty_team.pk]),
        )

    def test_task_cards_show_id_priority_and_assignee(self):
        self.client.force_login(self.developer)
        response = self.client.get(
            reverse('tracker:team_detail', args=[self.team.pk]),
        )
        self.assertContains(response, f'#{self.task.pk}')
        self.assertContains(response, self.task.get_priority_display())
        self.assertContains(response, self.developer.username)
