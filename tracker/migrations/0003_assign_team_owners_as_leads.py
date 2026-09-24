from django.db import migrations


def assign_team_owners_as_leads(apps, schema_editor):
    Team = apps.get_model('tracker', 'Team')
    TeamMember = apps.get_model('tracker', 'TeamMember')
    database = schema_editor.connection.alias

    teams = Team.objects.using(database).select_related(
        'product__company',
    ).iterator()
    for team in teams:
        TeamMember.objects.using(database).update_or_create(
            team_id=team.pk,
            user_id=team.product.company.owner_id,
            defaults={'role': 'LEAD'},
        )


class Migration(migrations.Migration):
    dependencies = [
        ('tracker', '0002_board_columns'),
    ]

    operations = [
        migrations.RunPython(
            assign_team_owners_as_leads,
            migrations.RunPython.noop,
        ),
    ]
