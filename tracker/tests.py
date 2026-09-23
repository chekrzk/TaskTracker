from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError, RestrictedError
from django.test import TestCase

from .models import BoardColumn, Comment, Company, Product, Task, Team, TeamMember


class TrackerModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.owner = user_model.objects.create_user(username='owner')
        cls.developer = user_model.objects.create_user(username='developer')
        cls.outsider = user_model.objects.create_user(username='outsider')
        cls.company = Company.objects.create(name='Example Corp', owner=cls.owner)
        cls.product = Product.objects.create(name='Marketplace', company=cls.company)
        cls.team = Team.objects.create(name='Backend', product=cls.product)
        cls.other_team = Team.objects.create(name='Frontend', product=cls.product)
        TeamMember.objects.create(
            team=cls.team, user=cls.developer, role=TeamMember.Role.DEVELOPER,
        )
        TeamMember.objects.create(team=cls.other_team, user=cls.outsider)
        cls.task = Task.objects.create(
            team=cls.team, column=cls.team.columns.first(), title='Login',
            author=cls.owner, assignee=cls.developer,
        )
        cls.comment = Comment.objects.create(
            task=cls.task, author=cls.developer, text='Готово к проверке',
        )

    def test_related_objects_form_the_expected_hierarchy(self):
        self.assertEqual(self.owner.owned_companies.get(), self.company)
        self.assertEqual(self.company.products.get(), self.product)
        self.assertCountEqual(self.product.teams.all(), [self.team, self.other_team])
        self.assertEqual(self.team.members.get(), self.developer)
        self.assertEqual(self.developer.teams.get(), self.team)
        self.assertEqual(self.team.tasks.get(), self.task)
        self.assertEqual(self.owner.authored_tasks.get(), self.task)
        self.assertEqual(self.developer.assigned_tasks.get(), self.task)
        self.assertEqual(self.task.comments.get(), self.comment)

    def test_duplicate_membership_is_rejected_by_database(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            TeamMember.objects.create(team=self.team, user=self.developer)

    def test_user_can_join_multiple_teams(self):
        membership = TeamMember.objects.create(
            team=self.other_team, user=self.developer,
        )
        self.assertEqual(membership.role, TeamMember.Role.MEMBER)
        self.assertCountEqual(self.developer.teams.all(), [self.team, self.other_team])

    def test_task_can_be_created_without_assignee_or_due_date(self):
        task = Task(team=self.team, column=self.team.columns.first(), title='Profile', author=self.owner)
        task.full_clean()
        task.save()
        task.refresh_from_db()
        self.assertIsNone(task.assignee)
        self.assertIsNone(task.due_date)
        self.assertEqual(task.type, Task.Type.TASK)
        self.assertEqual(task.column, self.team.columns.first())
        self.assertEqual(task.priority, Task.Priority.MEDIUM)
        self.assertIsNotNone(task.created_at)
        self.assertIsNotNone(task.updated_at)

    def test_task_accepts_member_of_its_team(self):
        self.task.full_clean()

    def test_task_rejects_assignee_from_another_team(self):
        self.task.assignee = self.outsider
        with self.assertRaises(ValidationError) as error:
            self.task.full_clean()
        self.assertIn('assignee', error.exception.message_dict)

    def test_changing_team_revalidates_assignee(self):
        self.task.team = self.other_team
        with self.assertRaises(ValidationError) as error:
            self.task.full_clean()
        self.assertIn('assignee', error.exception.message_dict)

    def test_invalid_task_choices_are_rejected(self):
        for field in ['type', 'priority']:
            with self.subTest(field=field):
                task = Task(team=self.team, column=self.team.columns.first(), title='Invalid choice', author=self.owner)
                setattr(task, field, 'INVALID')
                with self.assertRaises(ValidationError) as error:
                    task.full_clean()
                self.assertIn(field, error.exception.message_dict)

    def test_invalid_membership_role_is_rejected(self):
        membership = TeamMember(team=self.team, user=self.outsider, role='INVALID')
        with self.assertRaises(ValidationError) as error:
            membership.full_clean()
        self.assertIn('role', error.exception.message_dict)

    def test_required_text_fields_are_validated(self):
        for instance, field in [
            (Company(owner=self.owner), 'name'),
            (Product(company=self.company), 'name'),
            (Team(product=self.product), 'name'),
            (Task(team=self.team, column=self.team.columns.first(), author=self.owner), 'title'),
            (BoardColumn(team=self.team), 'name'),
            (Comment(task=self.task, author=self.owner), 'text'),
        ]:
            with self.subTest(model=type(instance).__name__):
                with self.assertRaises(ValidationError) as error:
                    instance.full_clean()
                self.assertIn(field, error.exception.message_dict)

    def test_deleting_assignee_keeps_task_without_assignment(self):
        assignee = get_user_model().objects.create_user(username='assignee')
        TeamMember.objects.create(team=self.team, user=assignee)
        self.task.assignee = assignee
        self.task.save()
        assignee.delete()
        self.task.refresh_from_db()
        self.assertIsNone(self.task.assignee)

    def test_owners_and_authors_are_protected_from_deletion(self):
        user_model = get_user_model()
        task_author = user_model.objects.create_user(username='task_author')
        comment_author = user_model.objects.create_user(username='comment_author')
        self.task.author = task_author
        self.task.save()
        self.comment.author = comment_author
        self.comment.save()
        for user in [self.owner, task_author, comment_author]:
            with self.subTest(username=user.username):
                with self.assertRaises(ProtectedError):
                    user.delete()

    def test_deleting_company_cascades_but_preserves_users(self):
        self.company.delete()
        for model in [Company, Product, Team, BoardColumn, TeamMember, Task, Comment]:
            with self.subTest(model=model.__name__):
                self.assertFalse(model.objects.exists())
        self.assertEqual(get_user_model().objects.count(), 3)

    def test_new_team_has_independent_default_columns(self):
        self.assertEqual(
            list(self.team.columns.values_list('name', flat=True)),
            ['TODO', 'IN PROGRESS', 'REVIEW', 'TESTING', 'DONE'],
        )
        self.assertFalse(
            self.team.columns.filter(pk__in=self.other_team.columns.values('pk')).exists()
        )
        self.team.name = 'Renamed team'
        self.team.save()
        self.assertEqual(self.team.columns.count(), 5)

    def test_custom_column_can_be_created_renamed_and_reordered(self):
        column = BoardColumn(team=self.team, name='Ожидает клиента', position=5)
        column.full_clean()
        column.save()
        self.task.column = column
        self.task.full_clean()
        self.task.save()
        column.name = 'Ожидает ответа'
        column.position = 0
        column.full_clean()
        column.save()
        self.task.refresh_from_db()
        self.assertEqual(self.task.column_id, column.pk)
        self.assertEqual(self.task.column.name, 'Ожидает ответа')
        self.assertEqual(list(self.team.columns.all())[1], column)

    def test_column_positions_can_be_swapped(self):
        first, second = list(self.team.columns.all())[:2]
        first.position, second.position = second.position, first.position
        first.save()
        second.save()
        self.assertEqual(list(self.team.columns.all())[:2], [second, first])

    def test_task_requires_column(self):
        task = Task(team=self.team, title='Missing column', author=self.owner)
        with self.assertRaises(ValidationError) as error:
            task.full_clean()
        self.assertIn('column', error.exception.message_dict)
        with self.assertRaises(IntegrityError), transaction.atomic():
            task.save()

    def test_task_rejects_column_from_another_team(self):
        self.task.column = self.other_team.columns.first()
        with self.assertRaises(ValidationError) as error:
            self.task.full_clean()
        self.assertIn('column', error.exception.message_dict)

    def test_column_with_tasks_cannot_change_team(self):
        column = self.task.column
        column.team = self.other_team
        with self.assertRaises(ValidationError) as error:
            column.full_clean()
        self.assertIn('team', error.exception.message_dict)

    def test_nonempty_column_cannot_be_deleted(self):
        with self.assertRaises(RestrictedError):
            self.task.column.delete()
        self.assertTrue(Task.objects.filter(pk=self.task.pk).exists())

    def test_column_can_be_deleted_after_tasks_are_moved(self):
        old_column = self.task.column
        self.task.column = self.team.columns.exclude(pk=old_column.pk).first()
        self.task.full_clean()
        self.task.save()
        old_column.delete()
        self.assertTrue(Task.objects.filter(pk=self.task.pk).exists())

    def test_column_position_cannot_be_negative(self):
        column = BoardColumn(team=self.team, name='Invalid position', position=-1)
        with self.assertRaises(ValidationError) as error:
            column.full_clean()
        self.assertIn('position', error.exception.message_dict)

    def test_deleting_team_cascades_columns_and_tasks(self):
        team_id = self.team.pk
        self.team.delete()
        self.assertFalse(BoardColumn.objects.filter(team_id=team_id).exists())
        self.assertFalse(Task.objects.filter(team_id=team_id).exists())
        self.assertTrue(Team.objects.filter(pk=self.other_team.pk).exists())
