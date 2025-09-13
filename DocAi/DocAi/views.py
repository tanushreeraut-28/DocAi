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
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from django.core.cache import cache
from django.conf import settings
import json
import logging

logger = logging.getLogger(__name__)

class FeaturesView(TemplateView):
    """
    Main features page view with dynamic content based on user status
    """
    template_name = 'features.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add dynamic content based on user authentication
        if self.request.user.is_authenticated:
            context.update({
                'user_tier': self.get_user_tier(),
                'available_features': self.get_available_features(),
                'usage_stats': self.get_user_usage_stats(),
                'show_upgrade_prompt': self.should_show_upgrade_prompt(),
            })
        else:
            context.update({
                'trial_features': self.get_trial_features(),
                'pricing_highlight': True,
            })
        
        # Add feature statistics and testimonials
        context.update({
            'feature_stats': self.get_feature_statistics(),
            'latest_updates': self.get_latest_feature_updates(),
            'demo_available': True,
        })
        
        return context
    
    def get_user_tier(self):
        """Get user's subscription tier"""
        if hasattr(self.request.user, 'subscription'):
            return self.request.user.subscription.tier
        return 'free'
    
    def get_available_features(self):
        """Get features available to current user based on their tier"""
        user_tier = self.get_user_tier()
        
        features = {
            'free': [
                'basic_verification',
                'pdf_support',
                'image_support',
                'basic_reports',
            ],
            'pro': [
                'basic_verification',
                'pdf_support',
                'image_support', 
                'basic_reports',
                'advanced_ai_detection',
                'batch_processing',
                'api_access',
                'detailed_reports',
                'priority_support',
            ],
            'enterprise': [
                'basic_verification',
                'pdf_support',
                'image_support',
                'basic_reports',
                'advanced_ai_detection',
                'batch_processing',
                'api_access',
                'detailed_reports',
                'priority_support',
                'blockchain_verification',
                'custom_ml_models',
                'white_label',
                'dedicated_support',
                'sla_guarantee',
            ]
        }
        
        return features.get(user_tier, features['free'])
    
    def get_user_usage_stats(self):
        """Get user's current usage statistics"""
        if not self.request.user.is_authenticated:
            return {}
        
        # This would typically come from your analytics/usage tracking model
        return {
            'documents_verified': 150,  # Replace with actual data
            'accuracy_rate': 99.2,
            'avg_processing_time': 1.8,
            'api_calls_this_month': 450,
        }
    
    def should_show_upgrade_prompt(self):
        """Determine if user should see upgrade prompts"""
        if not self.request.user.is_authenticated:
            return False
        
        user_tier = self.get_user_tier()
        # Show upgrade if user is on free tier or approaching limits
        return user_tier == 'free'
    
    def get_trial_features(self):
        """Get features available in trial version"""
        return [
            'basic_verification',
            'pdf_support',
            'image_support',
            'sample_reports',
            '10_free_verifications',
        ]
    
    def get_feature_statistics(self):
        """Get cached feature statistics for the page"""
        stats = cache.get('feature_statistics')
        if not stats:
            # These would typically come from your database
            stats = {
                'total_documents_processed': 5000000,
                'accuracy_rate': 99.8,
                'avg_processing_time': 2.3,
                'enterprise_clients': 180,
                'supported_formats': 50,
                'ai_models': 15,
                'security_checks': 247,
                'uptime_percentage': 99.9,
            }
            cache.set('feature_statistics', stats, 3600)  # Cache for 1 hour
        
        return stats
    
    def get_latest_feature_updates(self):
        """Get latest feature updates/announcements"""
        # This would typically come from a CMS or database
        return [
            {
                'title': 'New Blockchain Verification',
                'description': 'Immutable verification records now available',
                'date': '2025-09-01',
                'category': 'security'
            },
            {
                'title': 'Enhanced AI Models',
                'description': 'Improved accuracy for handwritten documents',
                'date': '2025-08-15',
                'category': 'ai'
            },
        ]

# Function-based view alternative
def features_view(request):
    """
    Simple function-based view for features page
    """
    context = {
        'page_title': 'Features - DocVerify',
        'meta_description': 'Discover DocVerify\'s advanced AI-powered document authentication features.',
    }
    
    # Add user-specific context
    if request.user.is_authenticated:
        context['user_authenticated'] = True
        # Add any user-specific data here
    
    return render(request, 'features.html', context)

@require_http_methods(["POST"])
@csrf_exempt
def track_feature_interaction(request):
    """
    Track user interactions with features page for analytics
    """
    try:
        data = json.loads(request.body)
        interaction_type = data.get('type')
        feature_name = data.get('feature')
        
        # Log the interaction
        logger.info(f"Feature interaction: {interaction_type} - {feature_name}")
        
        # Here you would typically save to your analytics database
        # analytics.track_interaction(request.user, interaction_type, feature_name)
        
        return JsonResponse({'status': 'success'})
    
    except Exception as e:
        logger.error(f"Error tracking feature interaction: {e}")
        return JsonResponse({'status': 'error'}, status=400)

@login_required
def demo_request(request):
    """
    Handle demo requests from authenticated users
    """
    if request.method == 'POST':
        user = request.user
        # Here you would typically:
        # 1. Create a demo request record
        # 2. Send notification to sales team
        # 3. Schedule demo or provide instant demo access
        
        messages.success(request, 'Demo request submitted! Our team will contact you within 24 hours.')
        return redirect('features')
    
    return redirect('features')

def feature_comparison(request):
    """
    Feature comparison page showing different tiers
    """
    comparison_data = {
        'tiers': [
            {
                'name': 'Free',
                'price': '$0',
                'features': [
                    {'name': 'Basic Verification', 'included': True},
                    {'name': 'PDF & Image Support', 'included': True},
                    {'name': '10 Documents/month', 'included': True},
                    {'name': 'Basic Reports', 'included': True},
                    {'name': 'Advanced AI Detection', 'included': False},
                    {'name': 'API Access', 'included': False},
                    {'name': 'Batch Processing', 'included': False},
                ]
            },
            {
                'name': 'Pro',
                'price': '$99',
                'features': [
                    {'name': 'Basic Verification', 'included': True},
                    {'name': 'PDF & Image Support', 'included': True},
                    {'name': '1,000 Documents/month', 'included': True},
                    {'name': 'Basic Reports', 'included': True},
                    {'name': 'Advanced AI Detection', 'included': True},
                    {'name': 'API Access', 'included': True},
                    {'name': 'Batch Processing', 'included': True},
                ]
            },
            {
                'name': 'Enterprise',
                'price': 'Custom',
                'features': [
                    {'name': 'Basic Verification', 'included': True},
                    {'name': 'PDF & Image Support', 'included': True},
                    {'name': 'Unlimited Documents', 'included': True},
                    {'name': 'Advanced Reports', 'included': True},
                    {'name': 'Advanced AI Detection', 'included': True},
                    {'name': 'API Access', 'included': True},
                    {'name': 'Batch Processing', 'included': True},
                ]
            }
        ]
    }
    
    return render(request, 'feature_comparison.html', comparison_data)

@require_http_methods(["GET"])
def feature_api_docs(request):
    """
    API documentation for developers
    """
    api_endpoints = [
        {
            'method': 'POST',
            'endpoint': '/api/v1/verify',
            'description': 'Verify a single document',
            'parameters': ['file', 'type', 'options']
        },
        {
            'method': 'POST', 
            'endpoint': '/api/v1/batch-verify',
            'description': 'Verify multiple documents',
            'parameters': ['files[]', 'options']
        },
        {
            'method': 'GET',
            'endpoint': '/api/v1/reports/{id}',
            'description': 'Get verification report',
            'parameters': ['id']
        }
    ]
    
    context = {
        'api_endpoints': api_endpoints,
        'api_key_required': True,
    }
    
    return render(request, 'api_docs.html', context)

class AjaxFeatureView(TemplateView):
    """
    AJAX view for loading feature details dynamically
    """
    
    def get(self, request, *args, **kwargs):
        feature_id = request.GET.get('feature_id')
        
        feature_details = {
            'ai_detection': {
                'title': 'AI-Powered Detection',
                'description': 'Advanced machine learning algorithms trained on millions of documents.',
                'benefits': [
                    'Detects sophisticated forgeries',
                    'Pixel-level analysis',
                    'Pattern recognition',
                    'Continuous learning'
                ],
                'accuracy': '99.8%'
            },
            'fast_processing': {
                'title': 'Lightning-Fast Processing',
                'description': 'Cloud-optimized infrastructure for real-time document verification.',
                'benefits': [
                    'Average 2.3 second processing',
                    'Parallel processing',
                    'Auto-scaling infrastructure',
                    'Global CDN delivery'
                ],
                'speed': '< 2.5s'
            },
            # Add more feature details as needed
        }
        
        feature = feature_details.get(feature_id, {})
        return JsonResponse(feature)
from django.shortcuts import render

def help_view(request):
    """
    Help page with FAQs and contact information
    """
    context = {
        'page_title': 'Help & Support',
        'meta_description': 'Get help with DocVerify document verification. FAQs and contact information.',
    }
    return render(request, 'help.html', context)
