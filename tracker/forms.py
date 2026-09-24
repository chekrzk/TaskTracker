from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import (
    BoardColumn, Comment, Company, Product, Task, Team, TeamMember,
)


class BootstrapFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')


class LoginForm(BootstrapFormMixin, AuthenticationForm):
    pass


class RegisterForm(BootstrapFormMixin, UserCreationForm):
    email = forms.EmailField(label='Email', required=True)

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ('username', 'email', 'first_name', 'last_name')

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Пользователь с таким email уже существует.')
        return email


class CompanyForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Company
        fields = ('name', 'description')
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5}),
        }


class ProductForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Product
        fields = ('name', 'description')
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5}),
        }


class TeamForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Team
        fields = ('name', 'description')
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5}),
        }


class TeamMemberForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = TeamMember
        fields = ('user', 'role')

    def __init__(self, *args, team, **kwargs):
        self.team = team
        super().__init__(*args, **kwargs)
        self.fields['user'].queryset = get_user_model().objects.order_by(
            'username', 'pk',
        )

    def clean_user(self):
        user = self.cleaned_data['user']
        if TeamMember.objects.filter(team=self.team, user=user).exists():
            raise forms.ValidationError('Пользователь уже состоит в этой команде.')
        return user



class BoardColumnForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = BoardColumn
        fields = ('name',)


class TaskForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Task
        fields = (
            'title',
            'description',
            'type',
            'priority',
            'assignee',
            'column',
            'due_date',
        )
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(
        self,
        *args,
        team,
        include_column=True,
        allow_assignment=True,
        **kwargs,
    ):
        self.team = team
        super().__init__(*args, **kwargs)
        self.fields['assignee'].queryset = get_user_model().objects.filter(
            team_memberships__team=team,
        ).distinct().order_by('username', 'pk')
        self.fields['column'].queryset = team.columns.order_by('position', 'pk')

        if not include_column:
            self.fields.pop('column')
        if not allow_assignment:
            self.fields['assignee'].disabled = True
            self.fields['assignee'].help_text = (
                'Назначать исполнителя может только Team Lead.'
            )



class CommentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Comment
        fields = ('text',)
        labels = {'text': 'Комментарий'}
        widgets = {
            'text': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Напишите комментарий',
            }),
        }
