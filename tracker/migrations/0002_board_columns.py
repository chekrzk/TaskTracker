from django.db import migrations, models
import django.db.models.deletion


def migrate_statuses_to_columns(apps, schema_editor):
    Team = apps.get_model('tracker', 'Team')
    BoardColumn = apps.get_model('tracker', 'BoardColumn')
    Task = apps.get_model('tracker', 'Task')
    alias = schema_editor.connection.alias
    defaults = [
        ('TODO', 'TODO'),
        ('IN_PROGRESS', 'IN PROGRESS'),
        ('REVIEW', 'REVIEW'),
        ('TESTING', 'TESTING'),
        ('DONE', 'DONE'),
    ]
    for team in Team.objects.using(alias).all().iterator():
        columns = {}
        for position, (status, name) in enumerate(defaults):
            column = BoardColumn.objects.using(alias).create(
                team_id=team.pk, name=name, position=position,
            )
            columns[status] = column.pk
        tasks = Task.objects.using(alias).filter(team_id=team.pk)
        # Preserve unexpected legacy values too, rather than dropping tasks.
        for status in tasks.values_list('status', flat=True).distinct():
            if status not in columns:
                column = BoardColumn.objects.using(alias).create(
                    team_id=team.pk, name=status or 'Без названия',
                    position=len(columns),
                )
                columns[status] = column.pk
            tasks.filter(status=status).update(column_id=columns[status])


class Migration(migrations.Migration):
    dependencies = [
        ('tracker', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='BoardColumn',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID',
                )),
                ('name', models.CharField(max_length=255, verbose_name='Название')),
                ('position', models.PositiveIntegerField(default=0, verbose_name='Порядок')),
                ('team', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='columns', to='tracker.team', verbose_name='Команда',
                )),
            ],
            options={
                'verbose_name': 'Колонка доски',
                'verbose_name_plural': 'Колонки доски',
                'ordering': ['position', 'pk'],
            },
        ),
        migrations.AddField(
            model_name='task',
            name='column',
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.RESTRICT,
                related_name='tasks', to='tracker.boardcolumn', verbose_name='Колонка',
            ),
        ),
        # Intentionally irreversible: custom columns cannot fit a fixed enum.
        migrations.RunPython(migrate_statuses_to_columns),
        migrations.RemoveField(model_name='task', name='status'),
        migrations.AlterField(
            model_name='task',
            name='column',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.RESTRICT,
                related_name='tasks', to='tracker.boardcolumn', verbose_name='Колонка',
            ),
        ),
    ]
