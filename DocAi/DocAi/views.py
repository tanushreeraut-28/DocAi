from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
import json
import re

# ==================== AUTHENTICATION VIEWS ====================

def home_view(request):
    """Main landing page view"""
    return render(request, 'base.html')


def login_view(request):
    """Handle user login"""
    if request.user.is_authenticated:
        return redirect('home')  # Redirect already authenticated users to home

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        remember_me = request.POST.get('remember-me', False)

        # Validate required fields
        if not email or not password:
            messages.error(request, 'Please fill in all fields.')
            return render(request, 'login.html')

        # Validate email format
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, 'Please enter a valid email address.')
            return render(request, 'login.html')

        # Authenticate user
        try:
            user_obj = User.objects.get(email=email)
            username = user_obj.username
        except User.DoesNotExist:
            messages.error(request, 'Invalid email or password.')
            return render(request, 'login.html')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                if not remember_me:
                    request.session.set_expiry(0)
                messages.success(request, f'Welcome back, {user.username}!')

                # Redirect to next page or home
                next_url = request.GET.get('next') or 'home'
                return redirect(next_url)
            else:
                messages.error(request, 'Your account has been disabled.')
        else:
            messages.error(request, 'Invalid email or password.')

    return render(request, 'login.html')


def register_view(request):
    """Handle user registration"""
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirmPassword', '')
        newsletter = request.POST.get('newsletter', False)
        terms = request.POST.get('terms', False)

        errors = []

        # Validate required fields
        if not all([username, email, password, confirm_password]):
            errors.append('Please fill in all required fields.')

        # Terms acceptance
        if not terms:
            errors.append('You must accept the Terms of Service and Privacy Policy.')

        # Username validation
        if len(username) < 3:
            errors.append('Username must be at least 3 characters long.')
        elif len(username) > 30:
            errors.append('Username must be less than 30 characters.')
        elif not re.match(r'^[a-zA-Z0-9_]+$', username):
            errors.append('Username can only contain letters, numbers, and underscores.')
        elif User.objects.filter(username=username).exists():
            errors.append('This username is already taken.')

        # Email validation
        try:
            validate_email(email)
            if User.objects.filter(email=email).exists():
                errors.append('An account with this email already exists.')
        except ValidationError:
            errors.append('Please enter a valid email address.')

        # Password validation
        if len(password) < 8:
            errors.append('Password must be at least 8 characters long.')
        elif not re.search(r'[A-Za-z]', password):
            errors.append('Password must contain at least one letter.')
        elif not re.search(r'\d', password):
            errors.append('Password must contain at least one number.')

        # Password confirmation
        if password != confirm_password:
            errors.append("Passwords don't match.")

        # If there are validation errors, show them
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'register.html')

        # Create user
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )
            user.save()

            # Optional: newsletter subscription logic
            if newsletter:
                pass  # Add newsletter logic here

            # Auto-login after registration (optional)
            login(request, user)
            messages.success(request, f'Account created successfully! Welcome, {user.username}.')
            return redirect('home')

        except Exception as e:
            messages.error(request, 'An error occurred while creating your account. Please try again.')
            return render(request, 'register.html')

    return render(request, 'register.html')


def logout_view(request):
    """Handle user logout"""
    if request.user.is_authenticated:
        username = request.user.username
        logout(request)
        messages.success(request, f'Goodbye, {username}! You have been logged out successfully.')
    return redirect('home')


# ==================== USER PROFILE ====================

@login_required
def profile_view(request):
    """User profile management"""
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()

        request.user.first_name = first_name
        request.user.last_name = last_name
        request.user.save()

        messages.success(request, 'Profile updated successfully!')
        return redirect('profile')

    return render(request, 'profile.html')


# ==================== AJAX VIEWS ====================

@csrf_exempt
def check_username_availability(request):
    """AJAX endpoint to check username availability"""
    if request.method == 'POST':
        data = json.loads(request.body)
        username = data.get('username', '').strip()

        if len(username) < 3:
            return JsonResponse({'available': False, 'message': 'Username too short'})

        is_available = not User.objects.filter(username=username).exists()
        message = 'Username is available!' if is_available else 'Username is already taken'

        return JsonResponse({'available': is_available, 'message': message})

    return JsonResponse({'available': False, 'message': 'Invalid request'})


@csrf_exempt
def check_email_availability(request):
    """AJAX endpoint to check email availability"""
    if request.method == 'POST':
        data = json.loads(request.body)
        email = data.get('email', '').strip()

        try:
            validate_email(email)
            is_available = not User.objects.filter(email=email).exists()
            message = 'Email is available!' if is_available else 'Email is already registered'

            return JsonResponse({'available': is_available, 'message': message})
        except ValidationError:
            return JsonResponse({'available': False, 'message': 'Invalid email format'})

    return JsonResponse({'available': False, 'message': 'Invalid request'})


# ==================== SUPPORT VIEWS ====================

def help_view(request):
    return render(request, 'help.html')


def contact_view(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        message = request.POST.get('message', '').strip()

        if all([name, email, message]):
            messages.success(request, 'Thank you for your message! We will get back to you soon.')
            return redirect('contact')
        else:
            messages.error(request, 'Please fill in all fields.')

    return render(request, 'contact.html')


def password_reset_request_view(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()

        try:
            validate_email(email)
            if User.objects.filter(email=email).exists():
                messages.success(request, 'Password reset instructions have been sent to your email.')
            else:
                messages.error(request, 'No account found with this email address.')
        except ValidationError:
            messages.error(request, 'Please enter a valid email address.')

    return render(request, 'password_reset.html')


# ==================== ERROR HANDLERS ====================

def handler404(request, exception):
    return render(request, '404.html', status=404)


def handler500(request):
    return render(request, '500.html', status=500)
