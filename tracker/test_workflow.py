import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import BoardColumn, Comment, Company, Product, Task, Team, TeamMember


class FinalWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.participant = get_user_model().objects.create_user(
            username='workflow-developer',
            email='developer@example.com',
            password='Developer-pass-123!',
        )

    def test_complete_user_workflow(self):
        register_response = self.client.post(
            reverse('tracker:register'),
            {
                'username': 'workflow-owner',
                'email': 'owner@example.com',
                'first_name': 'Workflow',
                'last_name': 'Owner',
                'password1': 'Strong-workflow-pass-938!',
                'password2': 'Strong-workflow-pass-938!',
            },
        )
        self.assertRedirects(register_response, reverse('tracker:home'))
        owner = get_user_model().objects.get(username='workflow-owner')
        self.assertEqual(int(self.client.session['_auth_user_id']), owner.pk)

        company_response = self.client.post(
            reverse('tracker:company_create'),
            {
                'name': 'Workflow Company',
                'description': 'Created in the final workflow',
            },
        )
        company = Company.objects.get(name='Workflow Company')
        self.assertEqual(company.owner, owner)
        self.assertRedirects(
            company_response,
            reverse('tracker:company_detail', args=[company.pk]),
        )

        product_response = self.client.post(
            reverse('tracker:product_create', args=[company.pk]),
            {
                'name': 'Workflow Product',
                'description': 'Product for the workflow',
            },
        )
        product = Product.objects.get(name='Workflow Product')
        self.assertEqual(product.company, company)
        self.assertRedirects(
            product_response,
            reverse('tracker:product_detail', args=[product.pk]),
        )

        team_response = self.client.post(
            reverse('tracker:team_create', args=[product.pk]),
            {
                'name': 'Workflow Team',
                'description': 'Team for the workflow',
            },
        )
        team = Team.objects.get(name='Workflow Team')
        self.assertRedirects(
            team_response,
            reverse('tracker:team_detail', args=[team.pk]),
        )
        self.assertEqual(team.columns.count(), 5)
        self.assertTrue(
            TeamMember.objects.filter(
                team=team,
                user=owner,
                role=TeamMember.Role.LEAD,
            ).exists(),
        )

        member_response = self.client.post(
            reverse('tracker:team_member_add', args=[team.pk]),
            {
                'user': self.participant.pk,
                'role': TeamMember.Role.DEVELOPER,
            },
        )
        self.assertRedirects(
            member_response,
            reverse('tracker:team_detail', args=[team.pk]),
        )
        self.assertTrue(
            TeamMember.objects.filter(
                team=team,
                user=self.participant,
                role=TeamMember.Role.DEVELOPER,
            ).exists(),
        )

        task_response = self.client.post(
            reverse('tracker:task_create', args=[team.pk]),
            {
                'title': 'Workflow task',
                'description': 'Created without an assignee',
                'type': Task.Type.TASK,
                'priority': Task.Priority.HIGH,
                'assignee': '',
                'due_date': '',
            },
        )
        task = Task.objects.get(title='Workflow task')
        self.assertRedirects(
            task_response,
            reverse('tracker:task_detail', args=[task.pk]),
        )
        self.assertEqual(task.author, owner)
        self.assertIsNone(task.assignee)

        assign_response = self.client.post(
            reverse('tracker:task_edit', args=[task.pk]),
            {
                'title': task.title,
                'description': task.description,
                'type': task.type,
                'priority': task.priority,
                'assignee': self.participant.pk,
                'column': task.column_id,
                'due_date': '',
            },
        )
        self.assertRedirects(
            assign_response,
            reverse('tracker:task_detail', args=[task.pk]),
        )
        task.refresh_from_db()
        self.assertEqual(task.assignee, self.participant)

        create_column_response = self.client.post(
            reverse('tracker:board_column_create', args=[team.pk]),
            {'name': 'READY'},
        )
        self.assertRedirects(
            create_column_response,
            reverse('tracker:team_detail', args=[team.pk]),
        )
        custom_column = BoardColumn.objects.get(team=team, name='READY')

        rename_column_response = self.client.post(
            reverse(
                'tracker:board_column_edit',
                args=[custom_column.pk],
            ),
            {'name': 'READY FOR QA'},
        )
        self.assertRedirects(
            rename_column_response,
            reverse('tracker:team_detail', args=[team.pk]),
        )
        custom_column.refresh_from_db()
        self.assertEqual(custom_column.name, 'READY FOR QA')

        ordered_ids = [
            custom_column.pk,
            *team.columns.exclude(pk=custom_column.pk).values_list(
                'pk',
                flat=True,
            ),
        ]
        reorder_response = self.client.post(
            reverse('tracker:board_columns_reorder', args=[team.pk]),
            {'column_ids': ordered_ids},
        )
        self.assertRedirects(
            reorder_response,
            reverse('tracker:team_detail', args=[team.pk]),
        )
        self.assertEqual(
            list(
                team.columns.order_by('position', 'pk').values_list(
                    'pk',
                    flat=True,
                ),
            ),
            ordered_ids,
        )

        move_response = self.client.post(
            reverse('tracker:task_column_update', args=[task.pk]),
            data=json.dumps({'column_id': custom_column.pk}),
            content_type='application/json',
        )
        self.assertEqual(
            move_response.json(),
            {'success': True, 'column_id': custom_column.pk},
        )
        task.refresh_from_db()
        self.assertEqual(task.column, custom_column)

        comment_response = self.client.post(
            reverse('tracker:comment_create', args=[task.pk]),
            {'text': 'Workflow completed'},
        )
        self.assertRedirects(
            comment_response,
            reverse('tracker:task_detail', args=[task.pk]),
        )
        self.assertTrue(
            Comment.objects.filter(
                task=task,
                author=owner,
                text='Workflow completed',
            ).exists(),
        )

        dashboard_response = self.client.get(reverse('tracker:home'))
        self.assertContains(dashboard_response, company.name)
        self.assertContains(dashboard_response, team.name)
        self.assertContains(dashboard_response, task.title)
        self.assertContains(dashboard_response, custom_column.name)

        logout_response = self.client.post(reverse('tracker:logout'))
        self.assertRedirects(logout_response, reverse('tracker:login'))
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertRedirects(
            self.client.get(reverse('tracker:home')),
            f"{reverse('tracker:login')}?next={reverse('tracker:home')}",
        )
