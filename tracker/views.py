from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import (
    CompanyForm,
    ProductForm,
    RegisterForm,
    TaskForm,
    TeamForm,
    TeamMemberForm,
)
from .models import BoardColumn, Company, Product, Task, Team, TeamMember


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


def _can_view_company(user, company):
    return (
        company.owner_id == user.pk
        or company.products.filter(teams__members=user).exists()
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
        'can_edit': company.owner_id == request.user.pk,
    })


@login_required
def company_edit(request, pk):
    company = _get_company(pk)
    if company.owner_id != request.user.pk:
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
    if company.owner_id != request.user.pk:
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


def _can_view_product(user, product):
    return (
        product.company.owner_id == user.pk
        or product.teams.filter(members=user).exists()
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
        'can_edit': product.company.owner_id == request.user.pk,
        'can_create_team': product.company.owner_id == request.user.pk,
    })


@login_required
def product_edit(request, pk):
    product = _get_product(pk)
    if product.company.owner_id != request.user.pk:
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


def _team_role(user, team):
    return TeamMember.objects.filter(
        team=team,
        user=user,
    ).values_list('role', flat=True).first()


def _is_team_lead(user, team):
    return _team_role(user, team) == TeamMember.Role.LEAD


def _can_create_task(user, team):
    return _team_role(user, team) in {
        TeamMember.Role.LEAD,
        TeamMember.Role.DEVELOPER,
    }


def _can_view_team(user, team):
    return (
        team.product.company.owner_id == user.pk
        or TeamMember.objects.filter(team=team, user=user).exists()
    )


def _can_manage_team(user, team):
    return (
        team.product.company.owner_id == user.pk
        or _is_team_lead(user, team)
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
    if product.company.owner_id != request.user.pk:
        raise PermissionDenied

    form = TeamForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        team = form.save(commit=False)
        team.product = product
        team.save()
        messages.success(request, 'Команда создана.')
        return redirect('tracker:team_detail', pk=team.pk)

    return render(request, 'tracker/teams/form.html', {
        'form': form,
        'product': product,
        'page_title': 'Новая команда',
        'submit_label': 'Создать команду',
    })


def _render_team_detail(request, team, member_form=None):
    can_manage = _can_manage_team(request.user, team)
    columns = team.columns.all()
    if member_form is None and can_manage:
        member_form = TeamMemberForm(team=team)

    return render(request, 'tracker/teams/detail.html', {
        'team': team,
        'memberships': team.memberships.all(),
        'columns': columns,
        'can_manage': can_manage,
        'can_create_task': (
            _can_create_task(request.user, team) and bool(columns)
        ),
        'member_form': member_form,
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
    if not _can_manage_team(request.user, team):
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
    if not _can_manage_team(request.user, team):
        raise PermissionDenied

    membership = get_object_or_404(
        TeamMember,
        pk=membership_id,
        team=team,
    )
    membership.delete()
    messages.success(request, 'Участник удалён из команды.')
    return redirect('tracker:team_detail', pk=team.pk)


def _get_task(pk):
    return get_object_or_404(
        Task.objects.select_related(
            'team',
            'team__product',
            'team__product__company',
            'team__product__company__owner',
            'column',
            'author',
            'assignee',
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

    is_lead = _is_team_lead(request.user, team)
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
        allow_assignment=is_lead,
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


@login_required
def task_detail(request, pk):
    task = _get_task(pk)
    if not _can_view_team(request.user, task.team):
        raise PermissionDenied

    return render(request, 'tracker/tasks/detail.html', {
        'task': task,
        'can_edit': _is_team_lead(request.user, task.team),
    })


@login_required
def task_edit(request, pk):
    task = _get_task(pk)
    if not _is_team_lead(request.user, task.team):
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
