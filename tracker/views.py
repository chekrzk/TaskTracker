from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import RegisterForm


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
