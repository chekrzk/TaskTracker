import json

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Max, Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import (
    BoardColumnForm,
    CommentForm,
    CompanyForm,
    ProductForm,
    RegisterForm,
    TaskForm,
    TeamForm,
    TeamMemberForm,
)
from .models import (
    BoardColumn, Comment, Company, Product, Task, Team, TeamMember,
)
from .permissions import (
    can_comment_task as _can_comment_task,
    can_create_product as _can_create_product,
    can_create_task as _can_create_task,
    can_create_team as _can_create_team,
    can_edit_company as _can_edit_company,
    can_edit_product as _can_edit_product,
    can_edit_task as _can_edit_task,
    can_manage_columns as _can_manage_columns,
    can_manage_members as _can_manage_members,
    can_manage_team as _can_manage_team,
    can_move_task as _can_move_task,
    can_view_company as _can_view_company,
    can_view_product as _can_view_product,
    can_view_team as _can_view_team,
    can_assign_task as _can_assign_task,
)


@login_required
def home(request):
    return render(request, 'tracker/home.html')


def register(request):
    if request.user.is_authenticated:
        return redirect('tracker:home')

    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect('tracker:home')

    return render(request, 'tracker/registration/register.html', {'form': form})


@login_required
def company_list(request):
    companies = Company.objects.filter(
        Q(owner=request.user) | Q(products__teams__members=request.user),
    ).select_related('owner').distinct().order_by('name', 'pk')
    return render(request, 'tracker/companies/list.html', {'companies': companies})


@login_required
def company_create(request):
    form = CompanyForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        company = form.save(commit=False)
        company.owner = request.user
        company.save()
        messages.success(request, 'Компания создана.')
        return redirect('tracker:company_detail', pk=company.pk)

    return render(request, 'tracker/companies/form.html', {
        'form': form,
        'page_title': 'Новая компания',
        'submit_label': 'Создать компанию',
    })


def _get_company(pk):
    return get_object_or_404(
        Company.objects.select_related('owner').prefetch_related('products'),
        pk=pk,
    )


@login_required
def company_detail(request, pk):
    company = _get_company(pk)
    if not _can_view_company(request.user, company):
        raise PermissionDenied

    if company.owner_id == request.user.pk:
        products = company.products.all()
    else:
        products = company.products.filter(teams__members=request.user).distinct()

    return render(request, 'tracker/companies/detail.html', {
        'company': company,
        'products': products,
        'can_edit': _can_edit_company(request.user, company),
    })


@login_required
def company_edit(request, pk):
    company = _get_company(pk)
    if not _can_edit_company(request.user, company):
        raise PermissionDenied

    form = CompanyForm(request.POST or None, instance=company)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Компания обновлена.')
        return redirect('tracker:company_detail', pk=company.pk)

    return render(request, 'tracker/companies/form.html', {
        'form': form,
        'company': company,
        'page_title': 'Редактирование компании',
        'submit_label': 'Сохранить',
    })


@login_required
def product_create(request, company_id):
    company = _get_company(company_id)
    if not _can_create_product(request.user, company):
        raise PermissionDenied

    form = ProductForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        product = form.save(commit=False)
        product.company = company
        product.save()
        messages.success(request, 'Продукт создан.')
        return redirect('tracker:product_detail', pk=product.pk)

    return render(request, 'tracker/products/form.html', {
        'form': form,
        'company': company,
        'page_title': 'Новый продукт',
        'submit_label': 'Создать продукт',
    })


def _get_product(pk):
    return get_object_or_404(
        Product.objects.select_related(
            'company', 'company__owner',
        ).prefetch_related('teams'),
        pk=pk,
    )


@login_required
def product_detail(request, pk):
    product = _get_product(pk)
    if not _can_view_product(request.user, product):
        raise PermissionDenied

    if product.company.owner_id == request.user.pk:
        teams = product.teams.all().order_by('name', 'pk')
    else:
        teams = product.teams.filter(members=request.user).distinct().order_by(
            'name', 'pk',
        )

    return render(request, 'tracker/products/detail.html', {
        'product': product,
        'teams': teams,
        'can_edit': _can_edit_product(request.user, product),
        'can_create_team': _can_create_team(request.user, product),
    })


@login_required
def product_edit(request, pk):
    product = _get_product(pk)
    if not _can_edit_product(request.user, product):
        raise PermissionDenied

    form = ProductForm(request.POST or None, instance=product)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Продукт обновлён.')
        return redirect('tracker:product_detail', pk=product.pk)

    return render(request, 'tracker/products/form.html', {
        'form': form,
        'company': product.company,
        'product': product,
        'page_title': 'Редактирование продукта',
        'submit_label': 'Сохранить',
    })


def _get_team(pk):
    task_queryset = Task.objects.select_related(
        'author', 'assignee',
    ).order_by('pk')
    column_queryset = BoardColumn.objects.prefetch_related(
        Prefetch('tasks', queryset=task_queryset),
    ).order_by('position', 'pk')
    membership_queryset = TeamMember.objects.select_related('user').order_by(
        'user__username', 'pk',
    )
    return get_object_or_404(
        Team.objects.select_related(
            'product', 'product__company', 'product__company__owner',
        ).prefetch_related(
            Prefetch('memberships', queryset=membership_queryset),
            Prefetch('columns', queryset=column_queryset),
        ),
        pk=pk,
    )


@login_required
def team_list(request):
    teams = Team.objects.filter(
        Q(product__company__owner=request.user) | Q(members=request.user),
    ).select_related(
        'product', 'product__company',
    ).distinct().order_by(
        'product__company__name', 'product__name', 'name', 'pk',
    )
    return render(request, 'tracker/teams/list.html', {'teams': teams})


@login_required
def team_create(request, product_id):
    product = _get_product(product_id)
    if not _can_create_team(request.user, product):
        raise PermissionDenied

    form = TeamForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        team = form.save(commit=False)
        team.product = product
        with transaction.atomic():
            team.save()
            TeamMember.objects.create(
                team=team,
                user=request.user,
                role=TeamMember.Role.LEAD,
            )
        messages.success(request, 'Команда создана. Вы назначены Team Lead.')
        return redirect('tracker:team_detail', pk=team.pk)

    return render(request, 'tracker/teams/form.html', {
        'form': form,
        'product': product,
        'page_title': 'Новая команда',
        'submit_label': 'Создать команду',
    })


def _render_team_detail(
    request,
    team,
    member_form=None,
    column_form=None,
    column_edit_form=None,
    editing_column_id=None,
):
    can_manage = _can_manage_team(request.user, team)
    can_manage_columns = _can_manage_columns(request.user, team)
    columns = team.columns.all()
    if member_form is None and can_manage:
        member_form = TeamMemberForm(team=team)
    if column_form is None and can_manage_columns:
        column_form = BoardColumnForm()

    return render(request, 'tracker/teams/detail.html', {
        'team': team,
        'memberships': team.memberships.all(),
        'columns': columns,
        'can_manage': can_manage,
        'can_manage_columns': can_manage_columns,
        'can_create_task': (
            _can_create_task(request.user, team) and bool(columns)
        ),
        'can_move_tasks': _can_move_task(request.user, team),
        'member_form': member_form,
        'column_form': column_form,
        'column_edit_form': column_edit_form,
        'editing_column_id': editing_column_id,
    })


@login_required
def team_detail(request, pk):
    team = _get_team(pk)
    if not _can_view_team(request.user, team):
        raise PermissionDenied
    return _render_team_detail(request, team)


@login_required
def team_edit(request, pk):
    team = _get_team(pk)
    if not _can_manage_team(request.user, team):
        raise PermissionDenied

    form = TeamForm(request.POST or None, instance=team)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Команда обновлена.')
        return redirect('tracker:team_detail', pk=team.pk)

    return render(request, 'tracker/teams/form.html', {
        'form': form,
        'product': team.product,
        'team': team,
        'page_title': 'Редактирование команды',
        'submit_label': 'Сохранить',
    })


@login_required
@require_POST
def team_member_add(request, team_id):
    team = _get_team(team_id)
    if not _can_manage_members(request.user, team):
        raise PermissionDenied

    form = TeamMemberForm(request.POST, team=team)
    if form.is_valid():
        membership = form.save(commit=False)
        membership.team = team
        membership.save()
        messages.success(request, 'Участник добавлен в команду.')
        return redirect('tracker:team_detail', pk=team.pk)

    return _render_team_detail(request, team, member_form=form)


@login_required
@require_POST
def team_member_delete(request, team_id, membership_id):
    team = _get_team(team_id)
    if not _can_manage_members(request.user, team):
        raise PermissionDenied

    membership = get_object_or_404(
        TeamMember,
        pk=membership_id,
        team=team,
    )
    membership.delete()
    messages.success(request, 'Участник удалён из команды.')
    return redirect('tracker:team_detail', pk=team.pk)


def _get_column(pk):
    return get_object_or_404(
        BoardColumn.objects.select_related(
            'team',
            'team__product',
            'team__product__company',
            'team__product__company__owner',
        ),
        pk=pk,
    )


@login_required
@require_POST
def board_column_create(request, team_id):
    team = _get_team(team_id)
    if not _can_manage_columns(request.user, team):
        raise PermissionDenied

    form = BoardColumnForm(request.POST)
    if form.is_valid():
        column = form.save(commit=False)
        column.team = team
        last_position = team.columns.aggregate(
            value=Max('position'),
        )['value']
        column.position = 0 if last_position is None else last_position + 1
        column.save()
        messages.success(request, 'Колонка создана.')
        return redirect('tracker:team_detail', pk=team.pk)

    return _render_team_detail(request, team, column_form=form)


@login_required
@require_POST
def board_column_edit(request, pk):
    column = _get_column(pk)
    if not _can_manage_columns(request.user, column.team):
        raise PermissionDenied

    form = BoardColumnForm(request.POST, instance=column)
    if form.is_valid():
        form.save()
        messages.success(request, 'Колонка переименована.')
        return redirect('tracker:team_detail', pk=column.team_id)

    team = _get_team(column.team_id)
    return _render_team_detail(
        request,
        team,
        column_edit_form=form,
        editing_column_id=column.pk,
    )


@login_required
@require_POST
def board_column_delete(request, pk):
    column = _get_column(pk)
    if not _can_manage_columns(request.user, column.team):
        raise PermissionDenied

    if column.tasks.exists():
        messages.error(
            request,
            'Сначала перенесите задачи в другую колонку.',
        )
        return redirect('tracker:team_detail', pk=column.team_id)

    team_id = column.team_id
    column.delete()
    messages.success(request, 'Колонка удалена.')
    return redirect('tracker:team_detail', pk=team_id)


@login_required
@require_POST
def board_columns_reorder(request, team_id):
    team = _get_team(team_id)
    if not _can_manage_columns(request.user, team):
        raise PermissionDenied

    raw_ids = request.POST.getlist('column_ids')
    try:
        submitted_ids = [int(value) for value in raw_ids]
    except (TypeError, ValueError):
        submitted_ids = None

    with transaction.atomic():
        columns = list(
            BoardColumn.objects.select_for_update().filter(
                team=team,
            ).order_by('pk'),
        )
        current_ids = [column.pk for column in columns]
        valid = (
            submitted_ids is not None
            and len(submitted_ids) == len(current_ids)
            and len(set(submitted_ids)) == len(submitted_ids)
            and set(submitted_ids) == set(current_ids)
        )
        if not valid:
            messages.error(
                request,
                'Передан некорректный порядок колонок.',
            )
            return redirect('tracker:team_detail', pk=team.pk)

        columns_by_id = {column.pk: column for column in columns}
        for position, column_id in enumerate(submitted_ids):
            columns_by_id[column_id].position = position
        BoardColumn.objects.bulk_update(columns, ['position'])

    messages.success(request, 'Порядок колонок сохранён.')
    return redirect('tracker:team_detail', pk=team.pk)


def _get_task(pk):
    comment_queryset = Comment.objects.select_related('author').order_by(
        'created_at', 'pk',
    )
    return get_object_or_404(
        Task.objects.select_related(
            'team',
            'team__product',
            'team__product__company',
            'team__product__company__owner',
            'column',
            'author',
            'assignee',
        ).prefetch_related(
            Prefetch('comments', queryset=comment_queryset),
        ),
        pk=pk,
    )


@login_required
def task_create(request, team_id):
    team = _get_team(team_id)
    if not _can_create_task(request.user, team):
        raise PermissionDenied

    first_column = team.columns.order_by('position', 'pk').first()
    if first_column is None:
        messages.error(
            request,
            'Нельзя создать задачу: сначала добавьте колонку на доску.',
        )
        return redirect('tracker:team_detail', pk=team.pk)

    can_assign = _can_assign_task(request.user, team)
    task = Task(
        team=team,
        author=request.user,
        column=first_column,
    )
    form = TaskForm(
        request.POST or None,
        instance=task,
        team=team,
        include_column=False,
        allow_assignment=can_assign,
    )
    if request.method == 'POST' and form.is_valid():
        task = form.save()
        messages.success(request, 'Задача создана.')
        return redirect('tracker:task_detail', pk=task.pk)

    return render(request, 'tracker/tasks/form.html', {
        'form': form,
        'team': team,
        'page_title': 'Новая задача',
        'submit_label': 'Создать задачу',
    })


def _render_task_detail(request, task, comment_form=None):
    can_comment = _can_comment_task(request.user, task.team)
    if comment_form is None and can_comment:
        comment_form = CommentForm()

    return render(request, 'tracker/tasks/detail.html', {
        'task': task,
        'comments': task.comments.all(),
        'can_edit': _can_edit_task(request.user, task.team),
        'can_comment': can_comment,
        'comment_form': comment_form,
    })


@login_required
def task_detail(request, pk):
    task = _get_task(pk)
    if not _can_view_team(request.user, task.team):
        raise PermissionDenied
    return _render_task_detail(request, task)


@login_required
@require_POST
def comment_create(request, task_id):
    task = _get_task(task_id)
    if not _can_comment_task(request.user, task.team):
        raise PermissionDenied

    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.task = task
        comment.author = request.user
        comment.save()
        messages.success(request, 'Комментарий добавлен.')
        return redirect('tracker:task_detail', pk=task.pk)

    return _render_task_detail(request, task, comment_form=form)


@login_required
@require_POST
def task_column_update(request, pk):
    task = _get_task(pk)
    if not _can_move_task(request.user, task.team):
        return JsonResponse({
            'success': False,
            'error': 'Недостаточно прав для перемещения задачи.',
        }, status=403)

    try:
        payload = json.loads(request.body or b'{}')
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({
            'success': False,
            'error': 'Некорректный JSON.',
        }, status=400)

    column_id = payload.get('column_id') if isinstance(payload, dict) else None
    if isinstance(column_id, bool) or not isinstance(column_id, int):
        return JsonResponse({
            'success': False,
            'error': 'column_id должен быть целым числом.',
        }, status=400)

    column = BoardColumn.objects.filter(
        pk=column_id,
        team=task.team,
    ).first()
    if column is None:
        return JsonResponse({
            'success': False,
            'error': 'Колонка не найдена в команде задачи.',
        }, status=400)

    task.column = column
    task.save(update_fields=('column', 'updated_at'))
    return JsonResponse({
        'success': True,
        'column_id': column.pk,
    })


@login_required
def task_edit(request, pk):
    task = _get_task(pk)
    if not _can_edit_task(request.user, task.team):
        raise PermissionDenied

    form = TaskForm(
        request.POST or None,
        instance=task,
        team=task.team,
        include_column=True,
        allow_assignment=True,
    )
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Задача обновлена.')
        return redirect('tracker:task_detail', pk=task.pk)

    return render(request, 'tracker/tasks/form.html', {
        'form': form,
        'team': task.team,
        'task': task,
        'page_title': 'Редактирование задачи',
        'submit_label': 'Сохранить',
    })
