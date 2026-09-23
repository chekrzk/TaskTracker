from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import BoardColumn, Comment, Company, Product, Task, Team, TeamMember


class TrackerAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.admin_user = users.objects.create_superuser(
            username='test_admin', email='admin@example.com', password='Admin-test-pass-123!',
        )
        cls.member = users.objects.create_user(username='member')
        cls.outsider = users.objects.create_user(username='outsider')
        cls.company = Company.objects.create(name='Company', owner=cls.admin_user)
        cls.product = Product.objects.create(name='Product', company=cls.company)
        cls.team = Team.objects.create(name='Backend', product=cls.product)
        cls.other_team = Team.objects.create(name='Frontend', product=cls.product)
        cls.membership = TeamMember.objects.create(team=cls.team, user=cls.member)
        cls.task = Task.objects.create(
            team=cls.team, column=cls.team.columns.first(),
            title='Existing task', author=cls.admin_user, assignee=cls.member,
        )
        cls.comment = Comment.objects.create(
            task=cls.task, author=cls.admin_user, text='Existing comment',
        )

    def setUp(self):
        self.client.force_login(self.admin_user)

    def admin_url(self, model, action, obj=None):
        args = [obj.pk] if obj else []
        return reverse(f'admin:tracker_{model._meta.model_name}_{action}', args=args)

    def task_data(self, **changes):
        data = {
            'team': self.team.pk, 'column': self.team.columns.first().pk,
            'title': 'New task', 'description': '', 'type': 'TASK',
            'priority': 'MEDIUM', 'author': self.admin_user.pk,
            'assignee': self.member.pk, 'due_date': '',
        }
        data.update(changes)
        return data

    def test_anonymous_and_nonstaff_users_cannot_access_admin(self):
        self.client.logout()
        url = self.admin_url(Task, 'changelist')
        self.assertRedirects(
            self.client.get(url), reverse('admin:login') + '?next=' + url,
        )
        self.client.force_login(self.member)
        self.assertRedirects(
            self.client.get(url), reverse('admin:login') + '?next=' + url,
        )

    def test_superuser_can_log_in_with_password(self):
        self.client.logout()
        self.assertTrue(self.client.login(
            username='test_admin', password='Admin-test-pass-123!',
        ))
        self.assertContains(self.client.get(reverse('admin:index')), 'Управление данными')

    def test_all_models_have_working_list_add_and_change_pages(self):
        objects = [
            self.company, self.product, self.team, self.membership,
            self.task.column, self.task, self.comment,
        ]
        for obj in objects:
            for action in ['changelist', 'add', 'change']:
                with self.subTest(model=type(obj).__name__, action=action):
                    url = self.admin_url(type(obj), action, obj if action == 'change' else None)
                    self.assertEqual(self.client.get(url).status_code, 200)

    def test_create_complete_hierarchy_through_admin_forms(self):
        def create(model, data):
            response = self.client.post(self.admin_url(model, 'add'), data)
            self.assertEqual(response.status_code, 302)
            return model.objects.latest('pk')

        company = create(Company, {
            'name': 'Admin Company', 'description': '', 'owner': self.admin_user.pk,
        })
        product = create(Product, {
            'name': 'Admin Product', 'description': '', 'company': company.pk,
        })
        team = create(Team, {
            'name': 'Admin Team', 'description': '', 'product': product.pk,
        })
        self.assertEqual(team.columns.count(), 5)
        membership = create(TeamMember, {
            'team': team.pk, 'user': self.member.pk, 'role': 'DEVELOPER',
        })
        column = create(BoardColumn, {
            'team': team.pk, 'name': 'Waiting for customer', 'position': 5,
        })
        task = create(Task, self.task_data(
            team=team.pk, column=column.pk, title='Admin task',
        ))
        comment = create(Comment, {
            'task': task.pk, 'author': self.admin_user.pk, 'text': 'Admin comment',
        })
        self.assertEqual(membership.team, team)
        self.assertEqual(task.column, column)
        self.assertEqual(task.assignee, self.member)
        self.assertEqual(comment.task, task)

    def test_task_form_rejects_foreign_column_and_assignee(self):
        response = self.client.post(
            self.admin_url(Task, 'add'),
            self.task_data(column=self.other_team.columns.first().pk, assignee=self.outsider.pk),
        )
        self.assertEqual(response.status_code, 200)
        errors = response.context['adminform'].form.errors
        self.assertIn('column', errors)
        self.assertIn('assignee', errors)
        self.assertFalse(Task.objects.filter(title='New task').exists())

    def test_membership_form_rejects_duplicate(self):
        response = self.client.post(self.admin_url(TeamMember, 'add'), {
            'team': self.team.pk, 'user': self.member.pk, 'role': 'LEAD',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['adminform'].form.errors)
        self.assertEqual(self.team.memberships.count(), 1)

    def test_task_can_be_edited_and_deleted(self):
        url = self.admin_url(Task, 'change', self.task)
        response = self.client.post(url, self.task_data(
            title='Updated task', priority='HIGH', column=self.team.columns.last().pk,
        ))
        self.assertEqual(response.status_code, 302)
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, 'Updated task')
        self.assertEqual(self.task.priority, 'HIGH')
        self.assertEqual(self.task.column, self.team.columns.last())
        response = self.client.post(
            self.admin_url(Task, 'delete', self.task), {'post': 'yes'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Task.objects.filter(pk=self.task.pk).exists())
        self.assertFalse(Comment.objects.filter(pk=self.comment.pk).exists())

    def test_column_with_tasks_cannot_be_deleted_through_admin(self):
        column = self.task.column
        url = self.admin_url(BoardColumn, 'delete', column)
        for response in [self.client.get(url), self.client.post(url, {'post': 'yes'})]:
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['protected'])
        self.assertTrue(BoardColumn.objects.filter(pk=column.pk).exists())
        self.assertTrue(Task.objects.filter(pk=self.task.pk).exists())

    def test_empty_column_can_be_deleted_through_admin(self):
        column = self.team.columns.last()
        response = self.client.post(
            self.admin_url(BoardColumn, 'delete', column), {'post': 'yes'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(BoardColumn.objects.filter(pk=column.pk).exists())

    def test_column_can_be_renamed_and_reordered_through_admin(self):
        column = self.task.column
        response = self.client.post(self.admin_url(BoardColumn, 'change', column), {
            'name': 'Ready', 'team': self.team.pk, 'position': 8,
        })
        self.assertEqual(response.status_code, 302)
        column.refresh_from_db()
        self.task.refresh_from_db()
        self.assertEqual(column.name, 'Ready')
        self.assertEqual(column.position, 8)
        self.assertEqual(self.task.column_id, column.pk)

    def test_company_cascade_delete_works_through_admin(self):
        response = self.client.post(
            self.admin_url(Company, 'delete', self.company), {'post': 'yes'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Company.objects.filter(pk=self.company.pk).exists())
        self.assertFalse(Task.objects.exists())
        self.assertFalse(BoardColumn.objects.exists())

    def test_column_choices_include_team_name(self):
        response = self.client.get(self.admin_url(Task, 'add'))
        self.assertContains(response, 'Backend — TODO')
        self.assertContains(response, 'Frontend — TODO')

    def test_owner_and_author_default_to_current_admin(self):
        for model, field in [(Company, 'owner'), (Task, 'author'), (Comment, 'author')]:
            with self.subTest(model=model.__name__):
                response = self.client.get(self.admin_url(model, 'add'))
                self.assertEqual(
                    response.context['adminform'].form.initial[field], self.admin_user.pk,
                )
