from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction


class Company(models.Model):
    name = models.CharField('Название', max_length=255)
    description = models.TextField('Описание', blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='owned_companies', verbose_name='Владелец',
    )
    created_at = models.DateTimeField('Создана', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлена', auto_now=True)

    class Meta:
        verbose_name = 'Компания'
        verbose_name_plural = 'Компании'

    def __str__(self):
        return self.name


class Product(models.Model):
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='products',
        verbose_name='Компания',
    )
    name = models.CharField('Название', max_length=255)
    description = models.TextField('Описание', blank=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Продукт'
        verbose_name_plural = 'Продукты'

    def __str__(self):
        return self.name


class Team(models.Model):
    DEFAULT_COLUMN_NAMES = ('TODO', 'IN PROGRESS', 'REVIEW', 'TESTING', 'DONE')

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='teams',
        verbose_name='Продукт',
    )
    name = models.CharField('Название', max_length=255)
    description = models.TextField('Описание', blank=True)
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through='TeamMember', related_name='teams',
        verbose_name='Участники',
    )
    created_at = models.DateTimeField('Создана', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлена', auto_now=True)

    class Meta:
        verbose_name = 'Команда'
        verbose_name_plural = 'Команды'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        creating = self._state.adding
        with transaction.atomic(using=kwargs.get('using') or self._state.db or 'default'):
            super().save(*args, **kwargs)
            if creating:
                BoardColumn.objects.using(self._state.db).bulk_create([
                    BoardColumn(team=self, name=name, position=position)
                    for position, name in enumerate(self.DEFAULT_COLUMN_NAMES)
                ])


class BoardColumn(models.Model):
    team = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name='columns',
        verbose_name='Команда',
    )
    name = models.CharField('Название', max_length=255)
    position = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Колонка доски'
        verbose_name_plural = 'Колонки доски'
        ordering = ['position', 'pk']

    def clean(self):
        super().clean()
        if self.pk and self.team_id:
            if self.tasks.exclude(team_id=self.team_id).exists():
                raise ValidationError({
                    'team': 'Нельзя перенести колонку с задачами в другую команду.',
                })

    def __str__(self):
        return self.name


class TeamMember(models.Model):
    class Role(models.TextChoices):
        LEAD = 'LEAD', 'Руководитель'
        DEVELOPER = 'DEVELOPER', 'Разработчик'
        TESTER = 'TESTER', 'Тестировщик'
        MEMBER = 'MEMBER', 'Участник'

    team = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name='memberships',
        verbose_name='Команда',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='team_memberships', verbose_name='Пользователь',
    )
    role = models.CharField('Роль', max_length=10, choices=Role, default=Role.MEMBER)
    joined_at = models.DateTimeField('Дата вступления', auto_now_add=True)

    class Meta:
        verbose_name = 'Участник команды'
        verbose_name_plural = 'Участники команд'
        constraints = [
            models.UniqueConstraint(
                fields=['team', 'user'], name='unique_team_member',
            ),
        ]

    def __str__(self):
        return f'{self.user} — {self.team}'


class Task(models.Model):
    class Type(models.TextChoices):
        TASK = 'TASK', 'Задача'
        BUG = 'BUG', 'Ошибка'
        STORY = 'STORY', 'История'

    class Priority(models.TextChoices):
        LOW = 'LOW', 'Низкий'
        MEDIUM = 'MEDIUM', 'Средний'
        HIGH = 'HIGH', 'Высокий'
        CRITICAL = 'CRITICAL', 'Критический'

    team = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name='tasks',
        verbose_name='Команда',
    )
    title = models.CharField('Название', max_length=255)
    description = models.TextField('Описание', blank=True)
    type = models.CharField('Тип', max_length=5, choices=Type, default=Type.TASK)
    column = models.ForeignKey(
        BoardColumn, on_delete=models.RESTRICT, related_name='tasks',
        verbose_name='Колонка',
    )
    priority = models.CharField(
        'Приоритет', max_length=8, choices=Priority, default=Priority.MEDIUM,
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='authored_tasks', verbose_name='Автор',
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        related_name='assigned_tasks', verbose_name='Исполнитель',
        blank=True, null=True,
    )
    created_at = models.DateTimeField('Создана', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлена', auto_now=True)
    due_date = models.DateField('Срок выполнения', blank=True, null=True)

    class Meta:
        verbose_name = 'Задача'
        verbose_name_plural = 'Задачи'

    def clean(self):
        super().clean()
        errors = {}
        if self.team_id and self.column_id:
            if not BoardColumn.objects.filter(
                pk=self.column_id, team_id=self.team_id,
            ).exists():
                errors['column'] = 'Колонка должна принадлежать команде задачи.'
        if self.team_id and self.assignee_id:
            if not TeamMember.objects.filter(
                team_id=self.team_id, user_id=self.assignee_id,
            ).exists():
                errors['assignee'] = 'Исполнитель должен состоять в команде задачи.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.title


class Comment(models.Model):
    task = models.ForeignKey(
        Task, on_delete=models.CASCADE, related_name='comments',
        verbose_name='Задача',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='task_comments', verbose_name='Автор',
    )
    text = models.TextField('Текст')
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Комментарий'
        verbose_name_plural = 'Комментарии'
        ordering = ['created_at', 'pk']

    def __str__(self):
        return self.text[:80]
