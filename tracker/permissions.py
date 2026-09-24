from types import MappingProxyType

from .models import TeamMember


class TeamCapability:
    MANAGE_TEAM = 'manage_team'
    MANAGE_MEMBERS = 'manage_members'
    MANAGE_COLUMNS = 'manage_columns'
    CREATE_TASK = 'create_task'
    EDIT_TASK = 'edit_task'
    ASSIGN_TASK = 'assign_task'
    MOVE_TASK = 'move_task'
    COMMENT_TASK = 'comment_task'


ROLE_CAPABILITIES = MappingProxyType({
    TeamMember.Role.LEAD: frozenset({
        TeamCapability.MANAGE_TEAM,
        TeamCapability.MANAGE_MEMBERS,
        TeamCapability.MANAGE_COLUMNS,
        TeamCapability.CREATE_TASK,
        TeamCapability.EDIT_TASK,
        TeamCapability.ASSIGN_TASK,
        TeamCapability.MOVE_TASK,
        TeamCapability.COMMENT_TASK,
    }),
    TeamMember.Role.DEVELOPER: frozenset({
        TeamCapability.CREATE_TASK,
        TeamCapability.MOVE_TASK,
        TeamCapability.COMMENT_TASK,
    }),
    TeamMember.Role.TESTER: frozenset({
        TeamCapability.MOVE_TASK,
        TeamCapability.COMMENT_TASK,
    }),
    TeamMember.Role.MEMBER: frozenset(),
})


def is_company_owner(user, company):
    return user.is_authenticated and company.owner_id == user.pk


def can_view_company(user, company):
    return (
        is_company_owner(user, company)
        or company.products.filter(teams__members=user).exists()
    )


def can_edit_company(user, company):
    return is_company_owner(user, company)


def can_create_product(user, company):
    return is_company_owner(user, company)


def can_view_product(user, product):
    return (
        is_company_owner(user, product.company)
        or product.teams.filter(members=user).exists()
    )


def can_edit_product(user, product):
    return is_company_owner(user, product.company)


def can_create_team(user, product):
    return is_company_owner(user, product.company)


def team_role(user, team):
    if not user.is_authenticated:
        return None
    return TeamMember.objects.filter(
        team=team,
        user=user,
    ).values_list('role', flat=True).first()


def has_team_capability(user, team, capability):
    role = team_role(user, team)
    return capability in ROLE_CAPABILITIES.get(role, ())


def is_team_lead(user, team):
    return team_role(user, team) == TeamMember.Role.LEAD


def can_view_team(user, team):
    return (
        is_company_owner(user, team.product.company)
        or team_role(user, team) is not None
    )


def can_manage_team(user, team):
    return has_team_capability(user, team, TeamCapability.MANAGE_TEAM)


def can_manage_members(user, team):
    return has_team_capability(user, team, TeamCapability.MANAGE_MEMBERS)


def can_manage_columns(user, team):
    return has_team_capability(user, team, TeamCapability.MANAGE_COLUMNS)


def can_create_task(user, team):
    return has_team_capability(user, team, TeamCapability.CREATE_TASK)


def can_edit_task(user, team):
    return has_team_capability(user, team, TeamCapability.EDIT_TASK)


def can_assign_task(user, team):
    return has_team_capability(user, team, TeamCapability.ASSIGN_TASK)


def can_move_task(user, team):
    return has_team_capability(user, team, TeamCapability.MOVE_TASK)


def can_comment_task(user, team):
    return has_team_capability(user, team, TeamCapability.COMMENT_TASK)
