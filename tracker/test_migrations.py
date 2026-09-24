import subprocess
import sys
import tempfile
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class BoardColumnMigrationTests(SimpleTestCase):
    def test_existing_tasks_keep_their_columns_and_relations(self):
        # A separate database allows testing the one-way data migration without
        # rolling back the test runner's current schema.
        script = """
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
from django.conf import settings
settings.DATABASES['default']['NAME'] = sys.argv[1]

import django
django.setup()

from django.db import connection
from django.db.migrations.executor import MigrationExecutor

executor = MigrationExecutor(connection)
old_target = [('tracker', '0001_initial')]
executor.migrate(old_target)
old_apps = executor.loader.project_state(old_target).apps
User = old_apps.get_model('auth', 'User')
Company = old_apps.get_model('tracker', 'Company')
Product = old_apps.get_model('tracker', 'Product')
Team = old_apps.get_model('tracker', 'Team')
TeamMember = old_apps.get_model('tracker', 'TeamMember')
Task = old_apps.get_model('tracker', 'Task')
Comment = old_apps.get_model('tracker', 'Comment')
user = User.objects.create(username='migration_user')
company = Company.objects.create(name='Company', owner=user)
product = Product.objects.create(name='Product', company=company)
teams = [
    Team.objects.create(name='Backend', product=product),
    Team.objects.create(name='Frontend', product=product),
]
empty_team = Team.objects.create(name='Empty', product=product)
expected = {}
for team in teams:
    TeamMember.objects.create(team=team, user=user, role='LEAD')
    for status in ['TODO', 'IN_PROGRESS', 'REVIEW', 'TESTING', 'DONE', 'CUSTOM']:
        task = Task.objects.create(
            team=team, title=status, status=status, author=user, assignee=user,
        )
        expected[task.pk] = (team.pk, status.replace('_', ' '), task.updated_at)
        Comment.objects.create(task=task, author=user, text='Keep me')

new_target = [('tracker', '0002_board_columns')]
executor = MigrationExecutor(connection)
executor.migrate(new_target)
apps = executor.loader.project_state(new_target).apps
Task = apps.get_model('tracker', 'Task')
BoardColumn = apps.get_model('tracker', 'BoardColumn')
Comment = apps.get_model('tracker', 'Comment')
TeamMember = apps.get_model('tracker', 'TeamMember')

assert Task.objects.count() == len(expected)
assert Comment.objects.count() == len(expected)
assert TeamMember.objects.count() == 2
assert BoardColumn.objects.filter(team_id=empty_team.pk).count() == 5
assert 'status' not in [field.name for field in Task._meta.fields]
for task in Task.objects.select_related('column'):
    team_id, name, updated_at = expected[task.pk]
    assert task.team_id == task.column.team_id == team_id
    assert task.column.name == name
    assert task.author_id == task.assignee_id == user.pk
    assert task.updated_at == updated_at
    assert task.comments.get().text == 'Keep me'
for team in teams:
    columns = BoardColumn.objects.filter(team_id=team.pk)
    assert list(columns.values_list('name', flat=True)) == [
        'TODO', 'IN PROGRESS', 'REVIEW', 'TESTING', 'DONE', 'CUSTOM',
    ]
    assert list(columns.values_list('position', flat=True)) == list(range(6))
"""
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, '-c', script, str(Path(directory) / 'migration.sqlite3')],
                cwd=settings.BASE_DIR,
                capture_output=True,
                text=True,
                timeout=60,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class RoleMigrationTests(SimpleTestCase):
    def test_existing_company_owners_become_team_leads(self):
        script = """
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
from django.conf import settings
settings.DATABASES['default']['NAME'] = sys.argv[1]

import django
django.setup()

from django.db import connection
from django.db.migrations.executor import MigrationExecutor

executor = MigrationExecutor(connection)
old_target = [('tracker', '0002_board_columns')]
executor.migrate(old_target)
old_apps = executor.loader.project_state(old_target).apps
User = old_apps.get_model('auth', 'User')
Company = old_apps.get_model('tracker', 'Company')
Product = old_apps.get_model('tracker', 'Product')
Team = old_apps.get_model('tracker', 'Team')
TeamMember = old_apps.get_model('tracker', 'TeamMember')

owner = User.objects.create(username='role_migration_owner')
member = User.objects.create(username='role_migration_member')
company = Company.objects.create(name='Company', owner=owner)
product = Product.objects.create(name='Product', company=company)
team_without_owner = Team.objects.create(name='Backend', product=product)
team_with_owner = Team.objects.create(name='Frontend', product=product)
TeamMember.objects.create(
    team=team_without_owner,
    user=member,
    role='MEMBER',
)
TeamMember.objects.create(
    team=team_with_owner,
    user=owner,
    role='DEVELOPER',
)

new_target = [('tracker', '0003_assign_team_owners_as_leads')]
executor = MigrationExecutor(connection)
executor.migrate(new_target)
apps = executor.loader.project_state(new_target).apps
TeamMember = apps.get_model('tracker', 'TeamMember')

assert TeamMember.objects.get(
    team_id=team_without_owner.pk,
    user_id=owner.pk,
).role == 'LEAD'
assert TeamMember.objects.get(
    team_id=team_with_owner.pk,
    user_id=owner.pk,
).role == 'LEAD'
assert TeamMember.objects.get(
    team_id=team_without_owner.pk,
    user_id=member.pk,
).role == 'MEMBER'
assert TeamMember.objects.filter(
    team_id=team_without_owner.pk,
    user_id=owner.pk,
).count() == 1
"""
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [
                    sys.executable,
                    '-c',
                    script,
                    str(Path(directory) / 'role-migration.sqlite3'),
                ],
                cwd=settings.BASE_DIR,
                capture_output=True,
                text=True,
                timeout=60,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
