from django import forms
from django.contrib import admin

from .models import BoardColumn, Comment, Company, Product, Task, Team, TeamMember


admin.site.site_header = 'Жир — администрирование'
admin.site.site_title = 'Жир'
admin.site.index_title = 'Управление данными'


class TaskAdminForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['column'].queryset = BoardColumn.objects.select_related('team')
        self.fields['column'].label_from_instance = (
            lambda column: f'{column.team.name} — {column.name}'
        )


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'created_at', 'updated_at']
    search_fields = ['name', 'description', 'owner__username']
    autocomplete_fields = ['owner']
    readonly_fields = ['created_at', 'updated_at']
    list_select_related = ['owner']
    date_hierarchy = 'created_at'

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        initial.setdefault('owner', request.user.pk)
        return initial


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'created_at', 'updated_at']
    list_filter = ['company']
    search_fields = ['name', 'description', 'company__name']
    autocomplete_fields = ['company']
    readonly_fields = ['created_at', 'updated_at']
    list_select_related = ['company']


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ['name', 'product', 'created_at', 'updated_at']
    list_filter = ['product__company', 'product']
    search_fields = ['name', 'description', 'product__name', 'product__company__name']
    autocomplete_fields = ['product']
    readonly_fields = ['created_at', 'updated_at']
    list_select_related = ['product']


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ['user', 'team', 'role', 'joined_at']
    list_filter = ['role', 'team']
    search_fields = ['user__username', 'user__email', 'team__name']
    autocomplete_fields = ['user', 'team']
    readonly_fields = ['joined_at']
    list_select_related = ['user', 'team']


@admin.register(BoardColumn)
class BoardColumnAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'team', 'position']
    list_display_links = ['id']
    list_editable = ['name', 'position']
    list_filter = ['team']
    search_fields = ['name', 'team__name']
    autocomplete_fields = ['team']
    list_select_related = ['team']
    ordering = ['team', 'position', 'pk']


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    form = TaskAdminForm
    list_display = [
        'id', 'title', 'team', 'column', 'type', 'priority', 'assignee', 'created_at',
    ]
    list_display_links = ['id', 'title']
    list_filter = ['team', 'column', 'type', 'priority']
    search_fields = ['title', 'description', 'team__name', 'assignee__username']
    autocomplete_fields = ['team', 'author', 'assignee']
    readonly_fields = ['created_at', 'updated_at']
    list_select_related = ['team', 'column', 'assignee']
    date_hierarchy = 'created_at'

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        initial.setdefault('author', request.user.pk)
        return initial


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['id', 'text_preview', 'task', 'author', 'created_at']
    search_fields = ['text', 'task__title', 'author__username']
    autocomplete_fields = ['task', 'author']
    readonly_fields = ['created_at', 'updated_at']
    list_select_related = ['task', 'author']
    date_hierarchy = 'created_at'

    @admin.display(description='Текст')
    def text_preview(self, obj):
        return str(obj)

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        initial.setdefault('author', request.user.pk)
        return initial
