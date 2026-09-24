from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .models import Comment, Company, Product, Task, Team, TeamMember


class CommentViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.owner = users.objects.create_user(
            username='comment-owner', password='Pass-12345!',
        )
        cls.lead = users.objects.create_user(
            username='comment-lead', password='Pass-12345!',
        )
        cls.developer = users.objects.create_user(
            username='comment-developer', password='Pass-12345!',
        )
        cls.tester = users.objects.create_user(
            username='comment-tester', password='Pass-12345!',
        )
        cls.member = users.objects.create_user(
            username='comment-member', password='Pass-12345!',
        )
        cls.outsider = users.objects.create_user(
            username='comment-outsider', password='Pass-12345!',
        )

        cls.company = Company.objects.create(
            name='Comment Company', owner=cls.owner,
        )
        cls.product = Product.objects.create(
            company=cls.company,
            name='Comment Product',
        )
        cls.team = Team.objects.create(
            product=cls.product,
            name='Comment Team',
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
            title='Discussed task',
            column=cls.team.columns.get(position=0),
            author=cls.lead,
        )
        cls.other_task = Task.objects.create(
            team=cls.team,
            title='Other task',
            column=cls.team.columns.get(position=0),
            author=cls.lead,
        )
        cls.first_comment = Comment.objects.create(
            task=cls.task,
            author=cls.developer,
            text='First comment',
        )
        cls.second_comment = Comment.objects.create(
            task=cls.task,
            author=cls.tester,
            text='Second comment',
        )

    def test_comment_endpoint_requires_authentication(self):
        url = reverse('tracker:comment_create', args=[self.task.pk])
        response = self.client.post(url, {'text': 'Anonymous'})
        self.assertRedirects(
            response,
            f"{reverse('tracker:login')}?next={url}",
        )

    def test_task_page_shows_comments_in_order(self):
        self.client.force_login(self.member)
        response = self.client.get(
            reverse('tracker:task_detail', args=[self.task.pk]),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'First comment')
        self.assertContains(response, 'Second comment')
        self.assertLess(
            response.content.index(b'First comment'),
            response.content.index(b'Second comment'),
        )
        self.assertContains(response, 'comment-developer')
        self.assertContains(response, 'comment-tester')
        self.assertNotContains(response, 'Добавить комментарий')

    def test_lead_developer_and_tester_can_comment(self):
        url = reverse('tracker:comment_create', args=[self.task.pk])
        for user in [self.lead, self.developer, self.tester]:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                text = f'Comment from {user.username}'
                response = self.client.post(url, {'text': text})
                self.assertRedirects(
                    response,
                    reverse('tracker:task_detail', args=[self.task.pk]),
                )
                comment = Comment.objects.get(text=text)
                self.assertEqual(comment.task, self.task)
                self.assertEqual(comment.author, user)

    def test_comment_form_is_visible_only_for_allowed_roles(self):
        detail_url = reverse('tracker:task_detail', args=[self.task.pk])
        create_url = reverse('tracker:comment_create', args=[self.task.pk])

        for user in [self.lead, self.developer, self.tester]:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(detail_url)
                self.assertContains(response, 'Добавить комментарий')
                self.assertContains(response, f'action="{create_url}"')

        for user in [self.owner, self.member]:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(detail_url)
                self.assertContains(response, 'First comment')
                self.assertNotContains(response, 'Добавить комментарий')
                self.assertNotContains(response, f'action="{create_url}"')

    def test_users_without_comment_role_get_403(self):
        url = reverse('tracker:comment_create', args=[self.task.pk])
        for user in [self.owner, self.member, self.outsider]:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertEqual(
                    self.client.post(
                        url,
                        {'text': 'Forbidden comment'},
                    ).status_code,
                    403,
                )
        self.assertFalse(
            Comment.objects.filter(text='Forbidden comment').exists(),
        )

    def test_task_and_author_are_set_from_url_and_request(self):
        self.client.force_login(self.lead)
        response = self.client.post(
            reverse('tracker:comment_create', args=[self.task.pk]),
            {
                'text': 'Protected relations',
                'task': self.other_task.pk,
                'author': self.outsider.pk,
            },
        )
        self.assertRedirects(
            response,
            reverse('tracker:task_detail', args=[self.task.pk]),
        )
        comment = Comment.objects.get(text='Protected relations')
        self.assertEqual(comment.task, self.task)
        self.assertEqual(comment.author, self.lead)

    def test_empty_comment_is_rejected(self):
        self.client.force_login(self.developer)
        response = self.client.post(
            reverse('tracker:comment_create', args=[self.task.pk]),
            {'text': '   '},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('text', response.context['comment_form'].errors)
        self.assertContains(response, 'First comment')
        self.assertEqual(
            Comment.objects.filter(task=self.task).count(),
            2,
        )

    def test_comment_html_is_escaped(self):
        Comment.objects.create(
            task=self.task,
            author=self.lead,
            text='<script>alert("xss")</script>',
        )
        self.client.force_login(self.member)
        response = self.client.get(
            reverse('tracker:task_detail', args=[self.task.pk]),
        )
        self.assertNotContains(response, '<script>', html=False)
        self.assertContains(
            response,
            '&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;',
            html=False,
        )

    def test_comment_creation_is_post_only_and_csrf_protected(self):
        url = reverse('tracker:comment_create', args=[self.task.pk])
        self.client.force_login(self.lead)
        self.assertEqual(self.client.get(url).status_code, 405)

        client = Client(enforce_csrf_checks=True)
        client.force_login(self.lead)
        self.assertEqual(
            client.post(url, {'text': 'No CSRF'}).status_code,
            403,
        )
        self.assertFalse(Comment.objects.filter(text='No CSRF').exists())

    def test_missing_task_returns_404(self):
        self.client.force_login(self.lead)
        self.assertEqual(
            self.client.post(
                reverse('tracker:comment_create', args=[999999]),
                {'text': 'Missing task'},
            ).status_code,
            404,
        )
