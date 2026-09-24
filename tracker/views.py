from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CompanyForm, ProductForm, RegisterForm
from .models import Company, Product


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
        teams = product.teams.filter(members=request.user).distinct().order_by('name', 'pk')

    return render(request, 'tracker/products/detail.html', {
        'product': product,
        'teams': teams,
        'can_edit': product.company.owner_id == request.user.pk,
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
