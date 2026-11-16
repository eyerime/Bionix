from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

from .forms import LoginForm, RegisterForm
from .models import UserProfile, UserStats


class BionixLoginView(LoginView):
    template_name = 'accounts/login.html'
    authentication_form = LoginForm
    redirect_authenticated_user = True


def register(request):
    """Create the user plus their 1-1 profile and stats rows, then sign in."""
    if request.user.is_authenticated:
        return redirect('dashboard:home')

    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        UserProfile.objects.get_or_create(user=user)
        UserStats.objects.get_or_create(user=user)
        login(request, user)
        messages.success(request, f'Welcome to BionixReader, {user.username}!')
        return redirect('dashboard:home')

    return render(request, 'accounts/register.html', {'form': form})
