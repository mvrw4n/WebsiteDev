from django.shortcuts import render, redirect
from django.views.generic import TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.decorators import user_passes_test
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django.http import HttpResponseForbidden, HttpResponse, JsonResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.renderers import TemplateHTMLRenderer, JSONRenderer
from django.template.loader import render_to_string
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
import logging
from .models import CustomUser, UserProfile, Interaction, PromptLog, AIAction, ScrapingStructure, ScrapingJob, Lead
from scraping.models import ScrapingResult, ScrapingTask
from .forms import LifetimeUserRegistrationForm
import json
from .utils.ai_utils import AIManager
import asyncio
from asgiref.sync import sync_to_async
from django.utils import timezone
from django.utils.timezone import now
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
from django.utils import timezone
from .serializers import LeadSerializer
from django.db.models import Q
from datetime import datetime, timedelta
from django.db.models import Sum
from django.db.models.functions import TruncDate
from django.db.models import Count

logger = logging.getLogger(__name__)
User = get_user_model()

class HomeView(TemplateView):
    template_name = 'home.html'

class PricingView(TemplateView):
    template_name = 'pricing.html'

class AboutView(TemplateView):
    template_name = 'about.html'

class LoginView(TemplateView):
    template_name = 'auth/login.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Include any tokens from the request if they exist
        if hasattr(self.request, 'auth_token'):
            context['auth_token'] = self.request.auth_token
        return context
        
    def dispatch(self, request, *args, **kwargs):
        # If user is already authenticated, redirect to dashboard
        if request.user.is_authenticated:
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

class RegisterView(TemplateView):
    template_name = 'auth/register.html'

class PasswordResetView(TemplateView):
    template_name = 'auth/password_reset.html'

class PasswordResetConfirmView(TemplateView):
    template_name = 'auth/password_reset_confirm.html'

class AccountActivationView(TemplateView):
    template_name = 'auth/activation.html'

class VerifyActivationCodeView(APIView):
    def post(self, request):
        code = request.data.get('code')
        email = request.data.get('email')
        
        if not code or not email:
            return Response(
                {'error': 'Both email and activation code are required.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(email=email, activation_code=code, is_active=False)
            user.is_active = True
            user.activation_code = None  # Clear the code after successful activation
            user.save()
            
            return Response({
                'message': 'Account activated successfully! You can now login.'
            })
            
        except User.DoesNotExist:
            return Response(
                {'error': 'Invalid activation code or email.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

class DashboardView(APIView):
    renderer_classes = [TemplateHTMLRenderer, JSONRenderer]
    template_name = 'dashboard.html'

    def get_or_create_profile(self, user):
        try:
            return user.profile
        except UserProfile.DoesNotExist:
            return UserProfile.objects.create(
                user=user,
                role='free',
                leads_quota=5,
                leads_used=0
            )

    def get_context_data(self, user):
        if not user.is_authenticated:
            return {
                'authentication_required': True,
                'message': 'Please log in to access the dashboard.'
            }

        profile = self.get_or_create_profile(user)
        context = {
            'user': {
                'email': user.email,
                'date_joined': user.date_joined,
                'is_active': user.is_active
            },
            'profile': {
                'role': profile.role
            }
        }

        # Generate JWT tokens for authenticated users
        if user.is_authenticated:
            refresh = RefreshToken.for_user(user)
            context['auth_token'] = {
                'access': str(refresh.access_token),
                'refresh': str(refresh)
            }

        if not user.is_active:
            context['activation_required'] = True
            context['message'] = 'Please activate your account to access all dashboard features. Check your email for the activation code.'
            return context

        # Available plans data
        available_plans = [
            {
                'id': 1,
                'name': 'Wizzy Free',
                'price': 0,
                'interval': 'mois',
                'leads_quota': 5,
                'features': [
                    '5 leads par mois',
                    'Accès basique aux fonctionnalités',
                    'Support par email'
                ]
            },
            {
                'id': 2,
                'name': 'Wizzy Classique',
                'price': 49,
                'interval': 'mois',
                'leads_quota': 100,
                'features': [
                    '100 leads par mois',
                    'Toutes les fonctionnalités',
                    'Support prioritaire',
                    'Achat de leads supplémentaires'
                ]
            },
            {
                'id': 3,
                'name': 'Wizzy Premium',
                'price': 99,
                'interval': 'mois',
                'leads_quota': 300,
                'features': [
                    '300 leads par mois',
                    'Toutes les fonctionnalités',
                    'Support VIP',
                    'Achat de leads supplémentaires',
                    'API Access'
                ]
            }
        ]

        # Current subscription data
        subscription_data = {
            'plan': {
                'name': profile.get_role_display(),
                'leads_quota': profile.leads_quota,
                'additional_leads': {
                    'min': 20,
                    'max': 30000
                }
            },
            'current_usage': {
                'leads_used': profile.leads_used if hasattr(profile, 'leads_used') else 0
            }
        }

        context.update({
            'subscription': subscription_data,
            'available_plans': available_plans
        })

        return context

    def get(self, request, *args, **kwargs):
        logger.debug(f"Request headers: {request.headers}")
        logger.debug(f"User authenticated: {request.user.is_authenticated}")
        logger.debug(f"User active: {request.user.is_active}")
        
        try:
            # Get context data for both authenticated and unauthenticated users
            context = self.get_context_data(request.user)
            
            # If user is not authenticated and requesting JSON, return 200 with message
            if not request.user.is_authenticated and 'application/json' in request.headers.get('Accept', ''):
                return Response(context)
            
            # If Accept header contains text/html, return HTML response
            if 'text/html' in request.headers.get('Accept', ''):
                return render(request, self.template_name, context)
            
            # Otherwise return JSON response
            return Response(context)
            
        except Exception as e:
            logger.error(f"Error in DashboardView: {str(e)}", exc_info=True)
            return Response(
                {'detail': 'An error occurred while processing your request.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ProtectedRegistrationView(TemplateView):
    template_name = 'registration/lifetime_registration.html'

    def get(self, request, *args, **kwargs):
        # Check if already authenticated
        if request.user.is_authenticated:
            messages.warning(request, 'You are already registered and logged in.')
            return redirect('dashboard')

        # If password is provided in session, show the form
        if request.session.get('can_access_lifetime_registration'):
            form = LifetimeUserRegistrationForm()
            return render(request, self.template_name, {'form': form, 'show_form': True})
        
        # Otherwise show password prompt
        return render(request, self.template_name, {'show_form': False})

    def post(self, request, *args, **kwargs):
        # Handle password verification
        if 'access_password' in request.POST:
            if request.POST['access_password'] == settings.LIFETIME_REGISTRATION_PASSWORD:
                request.session['can_access_lifetime_registration'] = True
                return render(request, self.template_name, {
                    'form': LifetimeUserRegistrationForm(),
                    'show_form': True
                })
            else:
                messages.error(request, 'Invalid password')
                return render(request, self.template_name, {'show_form': False})

        # Handle registration form
        if not request.session.get('can_access_lifetime_registration'):
            return HttpResponseForbidden()

        form = LifetimeUserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = True  # Auto-activate lifetime users
            user.save()

            # Create profile with notes including the reason
            UserProfile.objects.create(
                user=user,
                role='lifetime',
                unlimited_leads=True,
                notes=f"Lifetime free user\nReason: {form.cleaned_data['reason']}\nCompany: {form.cleaned_data['company']}\nCreated: {user.date_joined.strftime('%Y-%m-%d')}"
            )

            messages.success(request, 'Registration successful! You can now log in.')
            return redirect('auth:login')

        return render(request, self.template_name, {'form': form, 'show_form': True})

class ChatView(APIView):
    permission_classes = [IsAuthenticated]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ai_manager = AIManager()

    def post(self, request, format=None):
        """Handle incoming chat messages and return AI-generated responses."""
        try:
            # Get the message from the request
            message = request.data.get('message', None)
            
            if not message:
                return Response({"success": False, "error": "No message provided"}, status=400)
            
            # Get user context
            user = request.user
            username = user.email if user.is_authenticated else "Anonymous"
            
            # Check if there are previous interactions in the request
            previous_interactions = request.data.get('previous_interactions', None)
            
            # Get GDPR compliance mode from settings
            use_gdpr_compliance = settings.AI_CONFIG['mistral'].get('gdpr_compliance', {}).get('enabled_by_default', False)
            
            logger.info(f"📩 Received message from {username}: {message[:50]}... (GDPR mode: {use_gdpr_compliance})")
            
            # Process the message asynchronously
            try:
                # Create an event loop if necessary
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                # Create a user context dictionary instead of passing multiple separate arguments
                user_context = {
                    'username': username,
                    'previous_interactions': previous_interactions,
                    'use_gdpr_compliance': use_gdpr_compliance
                }
                
                # Run the AI manager's analyze method with the correct arguments
                # Since analyze_user_message is async, we need to await it properly
                coroutine = self.ai_manager.analyze_user_message(message, user_context)
                response = loop.run_until_complete(coroutine)
                
                # Log the response for debugging
                logger.debug(f"AI response for {username}: {response}")
                
                # Enhanced debug logging for structure detection
                logger.info(f"AI response keys: {list(response.keys())}")
                if 'structure_update' in response:
                    logger.info(f"Structure detected: {response['structure_update'].get('name', 'Unnamed')}")
                    logger.info(f"Structure type: {response['structure_update'].get('entity_type', 'Unknown')}")
                    fields_count = len(response['structure_update'].get('structure', []))
                    logger.info(f"Structure has {fields_count} fields")
                else:
                    logger.info("No structure_update found in AI response")
                
                # Check for errors in the response
                if not response or not isinstance(response, dict):
                    logger.error(f"Invalid response format from AI manager: {response}")
                    return Response({
                        "success": False,
                        "message": "Je suis désolé, j'ai rencontré un problème technique. Veuillez réessayer.",
                        "error": "Invalid response format"
                    }, status=500)
                
                # Check for error key in the response
                if "error" in response:
                    logger.warning(f"AI manager returned an error: {response.get('error')}")
                    # Return the response with the error message but mark as successful
                    # This allows the chat to display the friendly error message to the user
                    return Response({
                        "success": True,
                        "message": response.get("response_chat", "Je suis désolé, une erreur s'est produite."),
                        "ai_thinking": False,
                        "entity_type": None,
                        "scraping_strategy": None,
                        "error_info": response.get("error")
                    })
                
                # Format the response for the client
                ai_response = response.get("response_chat", "Je suis désolé, je n'ai pas compris.")
                actions_launched = response.get("actions_launched", "no_action")
                entity_type = response.get("entity_type", None)
                scraping_strategy = response.get("scraping_strategy", None)
                
                # Create a basic response to send back
                data = {
                    "success": True,
                    "message": ai_response,
                    "ai_thinking": False,
                    "entity_type": entity_type,
                    "scraping_strategy": scraping_strategy
                }
                
                # Check if a modification to a user-defined structure is needed
                if actions_launched == "update_structure":
                    logger.info("Structure update action detected")
                    structure_update = response.get("structure_update", {})
                    
                    # Validate the structure update
                    if not structure_update or not isinstance(structure_update, dict):
                        logger.warning("Invalid structure update format in AI response")
                        data["structure_update_status"] = "invalid_format"
                    else:
                        # Add the structure update to the response
                        data["structure_update"] = structure_update
                        data["structure_update_status"] = "pending"
                        logger.info(f"Structure update included in response: {structure_update}")
                
                # Additional logging for debugging
                logger.info(f"Final response keys: {list(data.keys())}")
                if 'structure_update' in data:
                    logger.info("Structure is being returned to frontend")
                else:
                    logger.warning("No structure_update in final response data")
                
                # Return the formatted response to the client
                return Response(data)
                
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                
                return Response({
                    "success": False, 
                    "message": "Je suis désolé, une erreur s'est produite lors du traitement de votre message. Notre équipe a été notifiée du problème.",
                    "error": str(e)
                }, status=500)
                
        except Exception as e:
            logger.error(f"Error in ChatView.post: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            return Response({
                "success": False, 
                "message": "Je suis désolé, une erreur inattendue s'est produite. Notre équipe a été notifiée du problème.",
                "error": str(e)
            }, status=500)


class ChatHistoryView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        """Load message history for the current user"""
        try:
            offset = int(request.query_params.get('offset', 0))
            limit = min(int(request.query_params.get('limit', 10)), 50)  # Max 50 at a time
            
            # Get interactions for the current user, ordered by created_at
            interactions = Interaction.objects.filter(user=request.user).order_by('-created_at')[offset:offset+limit]
            
            # Format into messages
            messages = []
            for interaction in interactions:
                # User message
                messages.append({
                    'id': interaction.id,
                    'is_user': True,
                    'message': interaction.message,
                    'created_at': interaction.created_at.isoformat()
                })
                
                # AI response
                messages.append({
                    'id': interaction.id,
                    'is_user': False,
                    'response': interaction.response,
                    'structure': interaction.structure,
                    'created_at': interaction.created_at.isoformat()
                })
                
                # Get associated actions
                actions = AIAction.objects.filter(interaction=interaction)
                if actions.exists():
                    for action in actions:
                        messages.append({
                            'id': interaction.id,
                            'action_id': action.id,
                            'is_user': False,
                            'is_action': True,
                            'action_type': action.action_type,
                            'status': action.status,
                            'parameters': action.parameters,
                            'created_at': action.created_at.isoformat()
                        })
            
            return Response({
                'messages': messages,
                'has_more': Interaction.objects.filter(user=request.user).count() > offset + limit
            })
            
        except Exception as e:
            logger.error(f"Error loading chat history: {str(e)}", exc_info=True)
            return Response(
                {'error': 'An error occurred while loading message history'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ChatJobsStatusView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        """Check status of chat-initiated jobs"""
        try:
            job_ids = request.data.get('job_ids', [])
            if not job_ids:
                return Response({'jobs': []})
                
            # Get actions for the given IDs that belong to this user
            actions = AIAction.objects.filter(
                id__in=job_ids,
                interaction__user=request.user
            ).select_related('interaction')
            
            # Format response
            jobs = []
            for action in actions:
                jobs.append({
                    'id': action.id,
                    'type': action.action_type,
                    'status': action.status,
                    'parameters': action.parameters,
                    'result': action.result,
                    'updated_at': action.updated_at.isoformat()
                })
                
            return Response({'jobs': jobs})
            
        except Exception as e:
            logger.error(f"Error checking job status: {str(e)}", exc_info=True)
            return Response(
                {'error': 'An error occurred while checking job status'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ChatClearView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        """Clear chat history for the current user"""
        try:
            # Delete all interactions for the user
            Interaction.objects.filter(user=request.user).delete()
            
            return Response({'success': True, 'message': 'Chat history cleared'})
            
        except Exception as e:
            logger.error(f"Error clearing chat history: {str(e)}", exc_info=True)
            return Response(
                {'error': 'An error occurred while clearing chat history'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ScrapingStructureView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, structure_id=None, *args, **kwargs):
        """Get all scraping structures for the current user or a specific one"""
        try:
            if structure_id:
                # Get specific structure
                structure = ScrapingStructure.objects.filter(id=structure_id, user=request.user).first()
                if not structure:
                    return Response(
                        {'error': 'Structure not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )
                    
                return Response({
                    'id': structure.id,
                    'name': structure.name,
                    'entity_type': structure.entity_type,
                    'structure': structure.structure,
                    'is_active': structure.is_active,
                    'scraping_strategy': structure.scraping_strategy,
                    'leads_target_per_day': structure.leads_target_per_day,
                    'created_at': structure.created_at.isoformat(),
                    'updated_at': structure.updated_at.isoformat(),
                    'display_name': self._get_display_name(structure)
                })
            
            # Get all structures for the current user
            structures = ScrapingStructure.objects.filter(user=request.user)
            data = []
            
            for structure in structures:
                data.append({
                    'id': structure.id,
                    'name': structure.name,
                    'entity_type': structure.entity_type,
                    'structure': structure.structure,
                    'is_active': structure.is_active,
                    'scraping_strategy': structure.scraping_strategy,
                    'leads_target_per_day': structure.leads_target_per_day,
                    'created_at': structure.created_at.isoformat(),
                    'display_name': self._get_display_name(structure)
                })
                
            return Response({'structures': data})
            
        except Exception as e:
            logger.error(f"Error retrieving scraping structures: {str(e)}", exc_info=True)
            return Response(
                {'error': 'An error occurred while retrieving scraping structures'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_display_name(self, structure):
        """Generate a display name for the structure based on its properties"""
        current_time = structure.created_at.strftime("%d/%m/%Y %H:%M")
        
        if structure.entity_type == 'mairie':
            if isinstance(structure.structure, dict) and 'mairie' in structure.structure:
                if 'infrastructure_sportive' in structure.structure['mairie'] and structure.structure['mairie']['infrastructure_sportive']:
                    if 'gazon_naturel' in structure.structure['mairie']['infrastructure_sportive'] or 'gazon_synthetique' in structure.structure['mairie']['infrastructure_sportive']:
                        return f"Mairies avec terrains de football"
                    else:
                        return f"Mairies avec infrastructures sportives"
                elif 'code_postal' in structure.structure['mairie'] and structure.structure['mairie']['code_postal']:
                    return f"Mairies - {structure.structure['mairie']['code_postal']}"
                else:
                    return f"Mairies - Données complètes"
            else:
                return f"Mairies - Collecte générale"
                
        elif structure.entity_type == 'entreprise':
            if isinstance(structure.structure, dict) and 'company' in structure.structure:
                if 'industry' in structure.structure['company'] and structure.structure['company']['industry']:
                    return f"Entreprises - {structure.structure['company']['industry']}"
                else:
                    return f"Entreprises - Données complètes"
            else:
                return f"Entreprises - Collecte générale"
                
        elif structure.entity_type == 'b2b_lead':
            if isinstance(structure.structure, dict) and 'company' in structure.structure:
                if 'industry' in structure.structure['company'] and structure.structure['company']['industry']:
                    return f"Leads B2B - {structure.structure['company']['industry']}"
                elif 'interet_ai' in structure.structure.get('company', {}) and structure.structure['company']['interet_ai']:
                    return f"Leads B2B - Intérêt IA"
                else:
                    return f"Leads B2B - Données complètes"
            else:
                return f"Leads B2B - Collecte générale"
        else:
            # For custom structures, include the scraping strategy in the name
            strategy_display = {
                'web_scraping': 'Web Scraping',
                'linkedin_scraping': 'LinkedIn Scraping',
                'custom_scraping': 'Scraping personnalisé'
            }.get(structure.scraping_strategy, 'Scraping personnalisé')
            
            return f"Structure {strategy_display} - {current_time}"
    
    def post(self, request, *args, **kwargs):
        """Save a new scraping structure"""
        try:
            name = request.data.get('name')
            entity_type = request.data.get('entity_type')
            structure_data = request.data.get('structure')
            scraping_strategy = request.data.get('scraping_strategy', 'custom_scraping')
            leads_target_per_day = int(request.data.get('leads_target_per_day', 10))
            
            if not all([name, entity_type, structure_data]):
                return Response(
                    {'error': 'Name, entity_type, and structure are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            # Check if structure with this name already exists
            existing = ScrapingStructure.objects.filter(user=request.user, name=name).first()
            if existing:
                # Update existing structure
                existing.entity_type = entity_type
                existing.structure = structure_data
                existing.is_active = True
                existing.scraping_strategy = scraping_strategy
                existing.leads_target_per_day = leads_target_per_day
                existing.save()
                
                return Response({
                    'success': True,
                    'message': 'Structure mise à jour avec succès',
                    'id': existing.id,
                    'display_name': self._get_display_name(existing)
                })
            
            # Create new structure
            structure = ScrapingStructure.objects.create(
                user=request.user,
                name=name,
                entity_type=entity_type,
                structure=structure_data,
                scraping_strategy=scraping_strategy,
                leads_target_per_day=leads_target_per_day
            )
            
            return Response({
                'success': True,
                'message': 'Structure enregistrée avec succès',
                'id': structure.id,
                'display_name': self._get_display_name(structure)
            })
            
        except Exception as e:
            logger.error(f"Error saving scraping structure: {str(e)}", exc_info=True)
            return Response(
                {'error': 'An error occurred while saving the structure'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def put(self, request, structure_id=None, *args, **kwargs):
        """Toggle structure active status or update leads_target_per_day"""
        try:
            if not structure_id:
                return Response(
                    {'error': 'Structure ID is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            structure = ScrapingStructure.objects.filter(id=structure_id, user=request.user).first()
            if not structure:
                return Response(
                    {'error': 'Structure not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
                
            # Toggle active status if no specific action is provided
            action = request.data.get('action')
            
            if action == 'set_target':
                # Update leads target per day
                leads_target = request.data.get('leads_target_per_day')
                if leads_target is not None:
                    structure.leads_target_per_day = int(leads_target)
                    structure.save()
                    return Response({
                        'success': True,
                        'message': 'Objectif de leads mis à jour',
                        'is_active': structure.is_active,
                        'leads_target_per_day': structure.leads_target_per_day
                    })
            else:
                # Toggle active status
                structure.is_active = not structure.is_active
                structure.save()
                
                status_msg = 'activée' if structure.is_active else 'désactivée'
                return Response({
                    'success': True,
                    'message': f'Structure {status_msg} avec succès',
                    'is_active': structure.is_active
                })
            
        except Exception as e:
            logger.error(f"Error updating scraping structure: {str(e)}", exc_info=True)
            return Response(
                {'error': 'An error occurred while updating the structure'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
    def delete(self, request, structure_id=None, *args, **kwargs):
        """Delete (deactivate) a scraping structure"""
        try:
            if not structure_id:
                return Response(
                    {'error': 'Structure ID is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            structure = ScrapingStructure.objects.filter(id=structure_id, user=request.user).first()
            if not structure:
                return Response(
                    {'error': 'Structure not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
                
            # Soft delete
            structure.is_active = False
            structure.save()
            
            return Response({
                'success': True,
                'message': 'Structure supprimée avec succès'
            })
            
        except Exception as e:
            logger.error(f"Error deleting scraping structure: {str(e)}", exc_info=True)
            return Response(
                {'error': 'An error occurred while deleting the structure'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ScrapingJobView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, job_id=None):
        try:
            if job_id:
                # Get specific job and verify ownership
                try:
                    job = ScrapingJob.objects.get(id=job_id, user=request.user)
                except ScrapingJob.DoesNotExist:
                    return Response({
                        'success': False,
                        'message': 'Job not found or access denied'
                    }, status=404)
                
                # Get job details
                job_data = job.to_dict()
                
                # Add task information if available
                task = job.get_active_task()
                if task:
                    job_data['task'] = {
                        'id': task.id,
                        'status': task.status,
                        'current_step': task.current_step,
                        'pages_explored': task.pages_explored,
                        'leads_found': task.leads_found,
                        'unique_leads': task.unique_leads,
                        'duration': task.duration
                    }
                
                return Response({
                    'success': True,
                    'job': job_data
                })
            else:
                # Get all jobs for the current user
                jobs = ScrapingJob.objects.filter(user=request.user).order_by('-created_at')
                return Response({
                    'success': True,
                    'jobs': [job.to_dict() for job in jobs],
                })
        except Exception as e:
            import traceback
            logger.error(f"Error in ScrapingJobView: {str(e)}\n{traceback.format_exc()}")
            return Response({'success': False, 'error': str(e)}, status=500)

    def post(self, request):
        try:
            # Get required fields
            name = request.data.get('name', '')
            structure_id = request.data.get('structure_id')
            search_query = request.data.get('search_query', '')
            leads_allocated = request.data.get('leads_allocated', 10)
            
            # Validate required fields
            if not structure_id:
                return Response({'success': False, 'error': 'Structure ID is required'}, status=400)
            
            # Get structure info for better naming
            structure_name = "Unknown Structure"
            try:
                structure = ScrapingStructure.objects.get(id=structure_id, user=request.user)
                structure_name = structure.name
            except Exception as e:
                logger.warning(f"Could not get structure name: {str(e)}")
                return Response({'success': False, 'error': f'Invalid structure: {str(e)}'}, status=400)
            
            # Create better job name if not provided
            if not name or name.startswith('Tâche pour structure'):
                current_time = now().strftime("%Y-%m-%d %H:%M")
                name = f"Manual scrape: {structure_name} - {current_time}"
            
            # Create new job
            job = ScrapingJob(
                name=name,
                search_query=search_query,
                leads_allocated=leads_allocated,
                status='initializing',
                user=request.user
            )
            
            # Set the structure
            job.structure_id = structure_id
            
            # Save the job
            job.save()
            
            # Start Celery task
            try:
                if hasattr(settings, 'USE_CELERY') and settings.USE_CELERY:
                    # Import directly depuis scraping.tasks et non depuis .tasks
                    from scraping.tasks import run_scraping_task
                    
                    # Créer d'abord une tâche ScrapingTask
                    from scraping.models import ScrapingTask, ScrapingLog
                    
                    # Créer la tâche de scraping
                    scraping_task = ScrapingTask.objects.create(
                        job=job,
                        status='pending',
                        current_step='Tâche en file d\'attente...'
                    )
                    
                    # Lancer la tâche Celery avec l'ID de la tâche de scraping
                    task_result = run_scraping_task.delay(scraping_task.id)
                    
                    # Mettre à jour la tâche avec l'ID Celery
                    scraping_task.celery_task_id = task_result.id
                    scraping_task.save()
                    
                    # Mettre à jour le job
                    job.task_id = task_result.id
                    job.status = 'running'
                    job.save()
                    
                    logger.info(f"Started Celery task {task_result.id} for job {job.id}")
                else:
                    # Use our local task simulation
                    from .tasks import start_scraping_job
                    result = start_scraping_job(job.id)
                    job.task_id = result.get('task_id')
                    job.status = 'running'
                    job.save()
                    logger.info(f"Started simulated task {job.task_id} for job {job.id}")
            except Exception as e:
                logger.error(f"Failed to start Celery task for job {job.id}: {str(e)}")
                # Don't fail the job creation if Celery fails
            
            return Response({
                'success': True,
                'job_id': job.id,
                'message': 'Job created successfully',
                'task_id': job.task_id
            })
            
        except Exception as e:
            import traceback
            logger.error(f"Error creating job: {str(e)}\n{traceback.format_exc()}")
            return Response({'success': False, 'error': str(e)}, status=500)

class ActiveScrapingJobsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            # Get active jobs for the current user
            active_jobs = ScrapingJob.objects.filter(
                user=request.user,
                status__in=['pending', 'running', 'paused']
            ).order_by('-created_at')

            # Format the jobs data
            jobs_data = []
            for job in active_jobs:
                job_data = job.to_dict()
                # Add task information if available
                task = job.get_active_task()
                if task:
                    job_data['task'] = {
                        'id': task.id,
                        'status': task.status,
                        'current_step': task.current_step,
                        'pages_explored': task.pages_explored,
                        'leads_found': task.leads_found,
                        'unique_leads': task.unique_leads,
                        'duration': task.duration
                    }
                jobs_data.append(job_data)

            return Response({
                'success': True,
                'active_jobs': jobs_data
            })
        except Exception as e:
            import traceback
            logger.error(f"Error in ActiveScrapingJobsView: {str(e)}\n{traceback.format_exc()}")
            return Response({'success': False, 'error': str(e)}, status=500)

class SubscriptionAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        """Get subscription information for the current user"""
        try:
            # Get user profile
            profile = request.user.profile
            
            # Get subscription info
            subscription = None
            if hasattr(request.user, 'subscription'):
                subscription = {
                    'plan_name': request.user.subscription.plan.name,
                    'status': request.user.subscription.status,
                    'current_period_end': request.user.subscription.current_period_end.isoformat(),
                    'cancel_at_period_end': request.user.subscription.cancel_at_period_end
                }
            
            # Get available plans
            available_plans = [
                {
                    'id': 1,
                    'name': 'Wizzy Free',
                    'price': 0,
                    'interval': 'mois',
                    'leads_quota': 5,
                    'features': [
                        '5 leads par mois',
                        'Accès basique aux fonctionnalités',
                        'Support par email'
                    ]
                },
                {
                    'id': 2,
                    'name': 'Wizzy Classique',
                    'price': 49,
                    'interval': 'mois',
                    'leads_quota': 100,
                    'features': [
                        '100 leads par mois',
                        'Toutes les fonctionnalités',
                        'Support prioritaire',
                        'Achat de leads supplémentaires'
                    ]
                },
                {
                    'id': 3,
                    'name': 'Wizzy Premium',
                    'price': 99,
                    'interval': 'mois',
                    'leads_quota': 300,
                    'features': [
                        '300 leads par mois',
                        'Toutes les fonctionnalités',
                        'Support VIP',
                        'Achat de leads supplémentaires',
                        'API Access'
                    ]
                }
            ]
            
            return Response({
                'subscription': subscription,
                'current_usage': {
                    'leads_used': profile.leads_used if hasattr(profile, 'leads_used') else 0,
                    'leads_quota': profile.leads_quota if hasattr(profile, 'leads_quota') else 5,
                    'leads_remaining': (profile.leads_quota - profile.leads_used) if hasattr(profile, 'leads_quota') and hasattr(profile, 'leads_used') else 5,
                    'unlimited_leads': getattr(profile, 'unlimited_leads', False)
                },
                'available_plans': available_plans,
                'profile': {
                    'role': profile.role,
                    'leads_quota': profile.leads_quota if hasattr(profile, 'leads_quota') else 5,
                    'leads_used': profile.leads_used if hasattr(profile, 'leads_used') else 0,
                    'unlimited_leads': getattr(profile, 'unlimited_leads', False)
                }
            })
            
        except Exception as e:
            logger.error(f"Error getting subscription info: {str(e)}", exc_info=True)
            return Response(
                {'error': 'An error occurred while getting subscription information'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self, request, *args, **kwargs):
        """Change user's subscription plan"""
        try:
            plan_id = request.data.get('plan_id')
            if not plan_id:
                return Response(
                    {'success': False, 'message': 'Plan ID is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get available plans from settings
            available_plans = [
                {'id': 1, 'name': 'Wizzy Free', 'leads_quota': 5, 'role': 'free'},
                {'id': 2, 'name': 'Wizzy Classique', 'leads_quota': 100, 'role': 'premium'},
                {'id': 3, 'name': 'Wizzy Premium', 'leads_quota': 300, 'role': 'premium_plus'}
            ]
            
            # Find selected plan
            selected_plan = None
            for plan in available_plans:
                if plan['id'] == int(plan_id):
                    selected_plan = plan
                    break
            
            if not selected_plan:
                return Response(
                    {'success': False, 'message': 'Invalid plan ID'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Update user profile
            profile = request.user.profile if hasattr(request.user, 'profile') else None
            if not profile:
                # Create profile if it doesn't exist
                profile = UserProfile.objects.create(
                    user=request.user,
                    role=selected_plan['role'],
                    leads_quota=selected_plan['leads_quota'],
                    leads_used=0
                )
            else:
                # Update existing profile
                profile.role = selected_plan['role']
                profile.leads_quota = selected_plan['leads_quota']
                profile.save()
            
            # TODO: Add actual payment processing integration here
            
            return Response({
                'success': True,
                'message': f'Plan mis à jour: {selected_plan["name"]}',
                'plan': {
                    'id': selected_plan['id'],
                    'name': selected_plan['name'],
                    'leads_quota': selected_plan['leads_quota'],
                    'role': selected_plan['role']
                }
            })
            
        except Exception as e:
            logger.error(f"Error changing subscription plan: {str(e)}", exc_info=True)
            return Response(
                {'success': False, 'message': 'An error occurred while changing your subscription plan'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class DashboardStatsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        """Get dashboard statistics for the current user"""
        try:
            # Get user profile - force refresh from database to ensure most current stats
            if hasattr(request.user, 'profile'):
                profile = request.user.profile
                # Explicitly refresh from the database
                from django.db import transaction
                with transaction.atomic():
                    profile.refresh_from_db()
            else:
                # Create profile if not exists
                from core.models import UserProfile
                profile = UserProfile.objects.create(user=request.user)
            
            # Reset daily leads if needed
            profile.reset_daily_leads()
            
            # Get scraping jobs stats
            total_jobs = ScrapingJob.objects.filter(user=request.user).count()
            active_jobs = ScrapingJob.objects.filter(
                user=request.user,
                status__in=['pending', 'running']
            ).count()
            
            # Get leads usage stats
            leads_used = profile.leads_used
            leads_quota = profile.leads_quota
            leads_remaining = leads_quota - leads_used if not profile.unlimited_leads else None
            
            # Get rate limiting and incomplete leads stats
            rate_limited_leads = getattr(profile, 'rate_limited_leads', 0) or 0
            incomplete_leads = getattr(profile, 'incomplete_leads', 0) or 0
            
            # Get total leads found from scraping tasks
            from scraping.models import ScrapingTask
            
            total_leads_found = ScrapingTask.objects.filter(
                job__user=request.user
            ).aggregate(
                total=Sum('leads_found'),
                unique=Sum('unique_leads'),
                rate_limited=Sum('rate_limited_leads'),
                incomplete=Sum('incomplete_leads'),
                duplicate=Sum('duplicate_leads')
            )
            
            # Ensure we don't have None values
            for key, value in total_leads_found.items():
                if value is None:
                    total_leads_found[key] = 0
            
            # Add task stats to profile stats for completeness
            rate_limited_leads += total_leads_found.get('rate_limited', 0) or 0
            incomplete_leads += total_leads_found.get('incomplete', 0) or 0
            
            # Get weekly leads data (leads created per day over the last 7 days)
            from core.models import Lead
            from django.db.models.functions import TruncDate
            from django.db.models import Count
            
            # Calculate the start date (7 days ago)
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=6)  # 7 days including today
            
            # Create a list of all dates in the range
            date_range = [start_date + timedelta(days=i) for i in range(7)]
            
            # Query leads created per day
            daily_leads = Lead.objects.filter(
                user=request.user,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date
            ).annotate(
                date=TruncDate('created_at')
            ).values('date').annotate(
                count=Count('id')
            ).order_by('date')
            
            # Convert query result to a dictionary for easier lookup
            daily_leads_dict = {item['date']: item['count'] for item in daily_leads}
            
            # Create the weekly data with all days included
            weekly_leads = []
            for date in date_range:
                formatted_date = date.strftime('%Y-%m-%d')
                weekly_leads.append({
                    'date': formatted_date,
                    'leads': daily_leads_dict.get(date, 0)
                })
            
            # Get structures data and their statistics
            structures_stats = []
            for structure in ScrapingStructure.objects.filter(user=request.user, is_active=True):
                # Ensure daily count is reset if needed
                structure.reset_daily_leads()
                
                # Calculate completion percentage
                completion = structure.get_completion_percentage()
                
                # Get total leads from this structure
                structure_leads = Lead.objects.filter(
                    user=request.user,
                    source__contains=structure.name
                ).count()
                
                structures_stats.append({
                    'id': structure.id,
                    'name': structure.name,
                    'type': structure.entity_type,
                    'daily_target': structure.leads_target_per_day,
                    'daily_current': structure.leads_extracted_today,
                    'daily_completion_percentage': completion,
                    'total_leads': structure.total_leads_extracted,
                    'created_leads': structure_leads
                })
            
            # Get subscription info
            subscription = None
            if hasattr(request.user, 'subscription'):
                subscription = {
                    'plan_name': request.user.subscription.plan.name,
                    'status': request.user.subscription.status,
                    'current_period_end': request.user.subscription.current_period_end.isoformat(),
                    'cancel_at_period_end': request.user.subscription.cancel_at_period_end
                }
            
            # Get recent activity
            recent_jobs = ScrapingJob.objects.filter(user=request.user).order_by('-created_at')[:5]
            recent_activity = [{
                'id': job.id,
                'name': job.name,
                'status': job.status,
                'leads_found': job.leads_found,
                'created_at': job.created_at.isoformat()
            } for job in recent_jobs]
            
            # Return the stats
            return Response({
                'jobs': {
                    'total': total_jobs,
                    'active': active_jobs
                },
                'leads': {
                    'used': leads_used,
                    'quota': leads_quota,
                    'remaining': leads_remaining,
                    'unlimited': profile.unlimited_leads,
                    'rate_limited': rate_limited_leads,
                    'incomplete': incomplete_leads
                },
                'scraping_stats': {
                    'total_leads_found': total_leads_found.get('total', 0) or 0,
                    'unique_leads': total_leads_found.get('unique', 0) or 0,
                    'rate_limited_leads': total_leads_found.get('rate_limited', 0) or 0,
                    'incomplete_leads': total_leads_found.get('incomplete', 0) or 0,
                    'duplicate_leads': total_leads_found.get('duplicate', 0) or 0
                },
                'subscription': subscription,
                'recent_activity': recent_activity,
                'weekly_leads': weekly_leads,
                'structures': structures_stats,
                'usage_stats': {
                    'leads_used': leads_used,
                    'leads_quota': leads_quota,
                    'leads_remaining': leads_remaining,
                    'unlimited_leads': profile.unlimited_leads,
                    'total_leads_found': total_leads_found.get('total', 0) or 0,
                    'rate_limited_leads': rate_limited_leads,
                    'incomplete_leads': incomplete_leads,
                    'active_jobs': active_jobs,
                    'total_jobs': total_jobs
                }
            })
            
        except Exception as e:
            logger.error(f"Error getting dashboard stats: {str(e)}", exc_info=True)
            return Response(
                {'error': 'An error occurred while getting dashboard statistics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ChatStructureUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        """Handle structure updates from the chat interface"""
        try:
            structure_data = request.data.get('structure')
            chat_id = request.data.get('chat_id')
            
            if not structure_data:
                return Response({'success': False, 'message': 'No structure data provided'}, status=400)
            
            # Validate structure data
            required_fields = ['name', 'entity_type', 'scraping_strategy']
            for field in required_fields:
                if field not in structure_data:
                    return Response({'success': False, 'message': f'Missing required field: {field}'}, status=400)
            
            # Create or update the structure
            try:
                # Check if structure with this name already exists
                existing = ScrapingStructure.objects.filter(user=request.user, name=structure_data['name']).first()
                
                if existing:
                    # Update existing structure
                    existing.entity_type = structure_data['entity_type']
                    existing.structure = structure_data.get('structure', [])
                    existing.is_active = True
                    existing.scraping_strategy = structure_data['scraping_strategy']
                    existing.leads_target_per_day = int(structure_data.get('leads_target_per_day', 10))
                    existing.save()
                    
                    structure_id = existing.id
                else:
                    # Create new structure
                    new_structure = ScrapingStructure.objects.create(
                        user=request.user,
                        name=structure_data['name'],
                        entity_type=structure_data['entity_type'],
                        structure=structure_data.get('structure', []),
                        scraping_strategy=structure_data['scraping_strategy'],
                        leads_target_per_day=int(structure_data.get('leads_target_per_day', 10))
                    )
                    
                    structure_id = new_structure.id
                
                # If chat_id is provided, update the interaction with structure info
                if chat_id:
                    # Try to convert to integer in case it's a string
                    try:
                        chat_id = int(chat_id)
                        interaction = Interaction.objects.filter(id=chat_id, user=request.user).first()
                        if interaction:
                            interaction.structure = structure_data
                            interaction.save()
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid chat_id provided for structure update: {chat_id}")
                
                return Response({
                    'success': True,
                    'message': 'Structure updated successfully',
                    'structure_id': structure_id
                })
                
            except Exception as e:
                logger.error(f"Error saving structure from chat: {str(e)}", exc_info=True)
                return Response({'success': False, 'message': f'Error saving structure: {str(e)}'}, status=500)
            
        except Exception as e:
            logger.error(f"Error handling structure update: {str(e)}", exc_info=True)
            return Response({'success': False, 'message': 'An error occurred'}, status=500)

class WorkerActivityView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get the activity of Celery workers"""
        try:
            # This is a mock response since we don't have a real worker activity endpoint yet
            mock_data = {
                'success': True,
                'active_workers': 1,
                'total_workers': 2,
                'activities': [
                    {
                        'worker_name': 'celery@worker1',
                        'hostname': 'worker1.example.com',
                        'status': 'running',
                        'activity_type': 'task_execution',
                        'activity_display': 'Exécution de tâche',
                        'timestamp': timezone.now().isoformat(),
                        'current_url': None,
                        'task': {
                            'id': 'task-123',
                            'job_name': 'Tâche de démonstration'
                        }
                    }
                ]
            }
            
            return Response(mock_data)
            
        except Exception as e:
            import traceback
            logger.error(f"Error getting worker activity: {str(e)}\n{traceback.format_exc()}")
            return Response({'success': False, 'error': str(e)}, status=500)

class ScrapingJobHistoryView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            # Get completed jobs for the current user
            completed_jobs = ScrapingJob.objects.filter(
                user=request.user,
                status__in=['completed', 'failed', 'stopped']
            ).order_by('-created_at')

            # Format the jobs data
            jobs_data = []
            for job in completed_jobs:
                job_data = job.to_dict()
                # Add task information if available
                task = job.get_active_task()
                if task:
                    job_data['task'] = {
                        'id': task.id,
                        'status': task.status,
                        'current_step': task.current_step,
                        'pages_explored': task.pages_explored,
                        'leads_found': task.leads_found,
                        'unique_leads': task.unique_leads,
                        'duration': task.duration
                    }
                jobs_data.append(job_data)

            return Response({
                'success': True,
                'history': jobs_data
            })
        except Exception as e:
            import traceback
            logger.error(f"Error in ScrapingJobHistoryView: {str(e)}\n{traceback.format_exc()}")
            return Response({'success': False, 'error': str(e)}, status=500)

class ScrapingJobControlView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, job_id):
        """Control a scraping job (stop, pause, resume, restart)"""
        try:
            # Parse the action from the request body
            action = request.data.get('action')
            
            if not action or action not in ['stop', 'pause', 'resume', 'restart']:
                return Response({'success': False, 'error': 'Invalid action'}, status=400)
            
            # Get the job and verify ownership
            try:
                job = ScrapingJob.objects.get(id=job_id, user=request.user)
            except ScrapingJob.DoesNotExist:
                return Response({'success': False, 'error': 'Job not found or access denied'}, status=404)
            
            # Handle the action
            if action == 'stop':
                job.status = 'stopped'
                job.save()
                logger.info(f"Job {job_id} stopped")
                
            elif action == 'pause':
                job.status = 'paused'
                job.save()
                logger.info(f"Job {job_id} paused")
                
            elif action == 'resume':
                job.status = 'running'
                job.save()
                logger.info(f"Job {job_id} resumed")
                
            elif action == 'restart':
                job.status = 'initializing'
                job.save()
                
                # Start a new Celery task
                try:
                    if hasattr(settings, 'USE_CELERY') and settings.USE_CELERY:
                        from scraping.tasks import run_scraping_task
                        
                        # Create a new scraping task
                        from scraping.models import ScrapingTask
                        scraping_task = ScrapingTask.objects.create(
                            job=job,
                            status='pending',
                            current_step='Tâche en file d\'attente...'
                        )
                        
                        # Start the Celery task
                        task_result = run_scraping_task.delay(scraping_task.id)
                        
                        # Update the task with the Celery task ID
                        scraping_task.celery_task_id = task_result.id
                        scraping_task.save()
                        
                        # Update the job
                        job.task_id = task_result.id
                        job.status = 'running'
                        job.save()
                        logger.info(f"Restarted Celery task {task_result.id} for job {job.id}")
                    else:
                        # Use our local task simulation
                        from .tasks import start_scraping_job
                        result = start_scraping_job(job.id)
                        job.task_id = result.get('task_id')
                        job.status = 'running'
                        job.save()
                        logger.info(f"Restarted simulated task {job.task_id} for job {job.id}")
                except Exception as e:
                    logger.error(f"Failed to restart Celery task for job {job.id}: {str(e)}")
                    return Response({'success': False, 'error': str(e)}, status=500)
            
            return Response({
                'success': True,
                'message': f'Job {action}ed successfully',
                'job_id': job.id,
                'status': job.status
            })
            
        except Exception as e:
            import traceback
            logger.error(f"Error controlling job: {str(e)}\n{traceback.format_exc()}")
            return Response({'success': False, 'error': str(e)}, status=500)

class UserProfileAPIView(APIView):
    """
    API endpoint for user profile management
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        """Get the user profile data"""
        try:
            # Get or create user profile
            try:
                profile = request.user.profile
            except UserProfile.DoesNotExist:
                profile = UserProfile.objects.create(
                    user=request.user,
                    role='free',
                    leads_quota=5,
                    leads_used=0
                )
            
            # Extract profile data
            profile_data = {
                'id': profile.id,
                'email': request.user.email,
                'date_joined': request.user.date_joined,
                'role': profile.role,
                'leads_quota': profile.leads_quota,
                'leads_used': profile.leads_used,
                'unlimited_leads': profile.unlimited_leads,
                'can_use_ai_chat': profile.can_use_ai_chat,
                'can_use_advanced_scraping': profile.can_use_advanced_scraping,
                'can_use_personalized_messages': profile.can_use_personalized_messages,
                'has_closer_team': profile.has_closer_team,
                'user_details': profile.user_details,
                'stats': {
                    'rate_limited_leads': profile.rate_limited_leads,
                    'incomplete_leads': profile.incomplete_leads
                }
            }
            
            return Response(profile_data)
            
        except Exception as e:
            logger.error(f"Error getting user profile: {str(e)}", exc_info=True)
            return Response(
                {'error': 'An error occurred while getting user profile'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self, request, *args, **kwargs):
        """Update the user profile"""
        try:
            # Get the profile or create it if it doesn't exist
            try:
                profile = request.user.profile
            except UserProfile.DoesNotExist:
                profile = UserProfile.objects.create(
                    user=request.user,
                    role='free',
                    leads_quota=5,
                    leads_used=0
                )
            
            # Update the profile with the provided data
            if 'role' in request.data and request.data['role'] in dict(UserProfile.ROLE_CHOICES):
                profile.role = request.data['role']
            
            # Update user_details if provided
            if 'user_details' in request.data and isinstance(request.data['user_details'], dict):
                # Merge with existing user_details or initialize if None
                current_details = profile.user_details or {}
                profile.user_details = {**current_details, **request.data['user_details']}
            
            # Save the updated profile
            profile.save()
            
            return Response({
                'success': True,
                'message': 'Profile updated successfully',
                'profile': {
                    'id': profile.id,
                    'email': request.user.email,
                    'date_joined': request.user.date_joined,
                    'role': profile.role,
                    'leads_quota': profile.leads_quota,
                    'leads_used': profile.leads_used,
                    'unlimited_leads': profile.unlimited_leads,
                    'can_use_ai_chat': profile.can_use_ai_chat,
                    'can_use_advanced_scraping': profile.can_use_advanced_scraping,
                    'can_use_personalized_messages': profile.can_use_personalized_messages,
                    'has_closer_team': profile.has_closer_team,
                    'user_details': profile.user_details,
                    'stats': {
                        'rate_limited_leads': profile.rate_limited_leads,
                        'incomplete_leads': profile.incomplete_leads
                    }
                }
            })
            
        except Exception as e:
            logger.error(f"Error updating user profile: {str(e)}", exc_info=True)
            return Response(
                {'error': 'An error occurred while updating user profile'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ScrapingRecommendationAPIView(APIView):
    """
    API endpoint for generating scraping structure recommendations
    based on user's industry information
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        """Generate scraping recommendations based on user profile"""
        try:
            # Get user profile
            try:
                profile = request.user.profile
            except UserProfile.DoesNotExist:
                return Response(
                    {'error': 'User profile not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Check if user_details exists
            if not profile.user_details:
                return Response({
                    'recommendations': [],
                    'message': 'Veuillez compléter votre profil pour obtenir des recommandations personnalisées'
                })
            
            user_details = profile.user_details
            industry = user_details.get('industry')
            company_size = user_details.get('company_size')
            business_model = user_details.get('business_model')
            targets = user_details.get('targets', {})
            
            if not industry:
                return Response({
                    'recommendations': [],
                    'message': 'Veuillez spécifier votre secteur d\'activité pour obtenir des recommandations'
                })
            
            # Generate recommendations based on industry and other factors
            recommendations = self._generate_recommendations(
                industry, 
                company_size, 
                business_model,
                targets
            )
            
            return Response({
                'recommendations': recommendations,
                'message': 'Recommandations générées avec succès'
            })
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}", exc_info=True)
            return Response(
                {'error': 'An error occurred while generating recommendations'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _generate_recommendations(self, industry, company_size, business_model, targets):
        """
        Generate scraping structure recommendations based on user profile
        """
        recommendations = []
        
        # Industry-based recommendations
        industry_recommendations = {
            'tech': [
                {
                    'title': 'LinkedIn Tech Companies',
                    'description': 'Structure pour extraire des leads de sociétés tech sur LinkedIn',
                    'fields': ['name', 'position', 'company', 'email', 'phone', 'location'],
                    'source': 'LinkedIn',
                    'confidence': 90
                },
                {
                    'title': 'GitHub Developers',
                    'description': 'Structure pour extraire des développeurs actifs sur GitHub',
                    'fields': ['username', 'name', 'email', 'repositories', 'location'],
                    'source': 'GitHub',
                    'confidence': 85
                }
            ],
            'retail': [
                {
                    'title': 'Retailers Directory',
                    'description': 'Structure pour extraire des détaillants et commerçants',
                    'fields': ['store_name', 'owner', 'email', 'phone', 'address', 'products'],
                    'source': 'Business directories',
                    'confidence': 88
                }
            ],
            'real_estate': [
                {
                    'title': 'Property Listings',
                    'description': 'Structure pour extraire des annonces immobilières',
                    'fields': ['property_type', 'price', 'location', 'size', 'contact_name', 'contact_email'],
                    'source': 'Real estate websites',
                    'confidence': 92
                },
                {
                    'title': 'Real Estate Agents',
                    'description': 'Structure pour extraire des agents immobiliers',
                    'fields': ['name', 'agency', 'email', 'phone', 'specialization', 'location'],
                    'source': 'Agency websites & directories',
                    'confidence': 86
                }
            ],
            'healthcare': [
                {
                    'title': 'Healthcare Professionals',
                    'description': 'Structure pour extraire des professionnels de santé',
                    'fields': ['name', 'specialty', 'facility', 'address', 'phone', 'email'],
                    'source': 'Medical directories',
                    'confidence': 89
                }
            ],
            'finance': [
                {
                    'title': 'Financial Advisors',
                    'description': 'Structure pour extraire des conseillers financiers',
                    'fields': ['name', 'company', 'certification', 'email', 'phone', 'specialization'],
                    'source': 'Financial services directories',
                    'confidence': 87
                }
            ],
            'education': [
                {
                    'title': 'Educational Institutions',
                    'description': 'Structure pour extraire des établissements éducatifs',
                    'fields': ['institution_name', 'type', 'contact_person', 'email', 'phone', 'address'],
                    'source': 'Educational directories',
                    'confidence': 91
                }
            ],
            'manufacturing': [
                {
                    'title': 'Manufacturing Companies',
                    'description': 'Structure pour extraire des entreprises manufacturières',
                    'fields': ['company_name', 'industry', 'products', 'contact_person', 'email', 'phone'],
                    'source': 'Industry directories',
                    'confidence': 84
                }
            ]
        }
        
        # Get basic recommendations for the industry
        if industry in industry_recommendations:
            recommendations.extend(industry_recommendations[industry])
        else:
            # Generic recommendation if industry not found
            recommendations.append({
                'title': 'Generic Business Contacts',
                'description': 'Structure générique pour extraire des contacts professionnels',
                'fields': ['name', 'position', 'company', 'email', 'phone'],
                'source': 'Multiple sources',
                'confidence': 70
            })
        
        # Adjust recommendations based on company size
        if company_size == 'small':
            recommendations.append({
                'title': 'Local Business Network',
                'description': 'Structure pour extraire des petites entreprises locales',
                'fields': ['business_name', 'owner', 'email', 'phone', 'address', 'business_type'],
                'source': 'Local business directories',
                'confidence': 82
            })
        elif company_size == 'medium':
            recommendations.append({
                'title': 'Mid-Market Companies',
                'description': 'Structure pour extraire des entreprises de taille moyenne',
                'fields': ['company_name', 'decision_maker', 'title', 'email', 'phone', 'industry', 'employee_count'],
                'source': 'Business databases',
                'confidence': 85
            })
        elif company_size == 'large':
            recommendations.append({
                'title': 'Enterprise Organizations',
                'description': 'Structure pour extraire des grandes entreprises et leurs départements',
                'fields': ['company_name', 'department', 'executive_name', 'title', 'email', 'phone', 'linkedin'],
                'source': 'Corporate databases',
                'confidence': 88
            })
        
        # Adjust based on target geography
        target_geography = targets.get('geography')
        if target_geography:
            if target_geography == 'local':
                recommendations.append({
                    'title': 'Local Market Contacts',
                    'description': 'Structure pour extraire des contacts dans votre zone géographique locale',
                    'fields': ['name', 'business', 'address', 'email', 'phone', 'distance'],
                    'source': 'Local directories',
                    'confidence': 93
                })
            elif target_geography == 'national':
                recommendations.append({
                    'title': 'National Business Network',
                    'description': 'Structure pour extraire des contacts à l\'échelle nationale',
                    'fields': ['name', 'company', 'region', 'email', 'phone', 'industry'],
                    'source': 'National business databases',
                    'confidence': 87
                })
            elif target_geography == 'international':
                recommendations.append({
                    'title': 'International Contacts',
                    'description': 'Structure pour extraire des contacts internationaux',
                    'fields': ['name', 'company', 'country', 'email', 'phone', 'language', 'timezone'],
                    'source': 'International directories',
                    'confidence': 81
                })
        
        # Add a custom recommendation based on scraping objectives
        objectives = targets.get('objectives')
        if objectives == 'lead_generation':
            recommendations.append({
                'title': 'Lead Generation Optimized',
                'description': 'Structure optimisée pour la génération de leads qualifiés',
                'fields': ['name', 'position', 'company', 'email', 'phone', 'linkedin', 'interest_indicators'],
                'source': 'Multiple platforms',
                'confidence': 89
            })
        elif objectives == 'market_research':
            recommendations.append({
                'title': 'Market Research Dataset',
                'description': 'Structure pour collecter des données de recherche de marché',
                'fields': ['company', 'product', 'price', 'features', 'region', 'market_share'],
                'source': 'Industry websites & reports',
                'confidence': 86
            })
        elif objectives == 'competitive_analysis':
            recommendations.append({
                'title': 'Competitor Analysis',
                'description': 'Structure pour analyser vos concurrents',
                'fields': ['competitor_name', 'products', 'pricing', 'unique_selling_points', 'customer_reviews', 'market_position'],
                'source': 'Company websites & review platforms',
                'confidence': 90
            })
            
        return recommendations

class UserLeadsAPIView(APIView):
    """
    API endpoint for user leads management
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        """Get leads for the current user"""
        try:
            # Get pagination parameters
            page = int(request.GET.get('page', 1))
            per_page = int(request.GET.get('per_page', 20))
            filter_type = request.GET.get('filter', 'all')
            
            # Calculate offset for pagination
            offset = (page - 1) * per_page
            
            # Get all scraping jobs for the current user
            user_jobs = ScrapingJob.objects.filter(user=request.user)
            
            # Get all tasks related to these jobs
            tasks = ScrapingTask.objects.filter(job__in=user_jobs)
            
            # Build query for lead results based on filter
            leads_query = ScrapingResult.objects.filter(task__in=tasks)
            
            if filter_type == 'processed':
                leads_query = leads_query.filter(is_processed=True)
            elif filter_type == 'unprocessed':
                leads_query = leads_query.filter(is_processed=False)
            elif filter_type == 'recent':
                # Last 7 days
                seven_days_ago = timezone.now() - timezone.timedelta(days=7)
                leads_query = leads_query.filter(created_at__gte=seven_days_ago)
            
            # Get total count
            total_count = leads_query.count()
            
            # Get paginated results
            leads = leads_query.order_by('-created_at')[offset:offset+per_page]
            
            # Format the results
            results = []
            for lead in leads:
                results.append({
                    'id': lead.id,
                    'lead_data': lead.lead_data,
                    'source_url': lead.source_url,
                    'is_processed': lead.is_processed,
                    'is_duplicate': lead.is_duplicate,
                    'created_at': lead.created_at.isoformat()
                })
            
            return Response({
                'total': total_count,
                'page': page,
                'per_page': per_page,
                'results': results
            })
            
        except Exception as e:
            logger.error(f"Error getting user leads: {str(e)}", exc_info=True)
            return Response(
                {'error': 'An error occurred while getting user leads'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self, request, lead_id=None, *args, **kwargs):
        """Update a lead status"""
        try:
            # Check if lead_id is provided
            if not lead_id:
                return Response(
                    {'error': 'Lead ID is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get the lead
            lead = ScrapingResult.objects.get(id=lead_id)
            
            # Check if the lead belongs to one of the user's tasks
            user_jobs = ScrapingJob.objects.filter(user=request.user)
            tasks = ScrapingTask.objects.filter(job__in=user_jobs)
            
            if lead.task not in tasks:
                return Response(
                    {'error': 'You do not have permission to update this lead'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Update the lead status
            action = request.data.get('action')
            if action == 'mark_processed':
                lead.is_processed = True
                lead.save()
                return Response({'success': True, 'message': 'Lead marked as processed'})
            elif action == 'mark_unprocessed':
                lead.is_processed = False
                lead.save()
                return Response({'success': True, 'message': 'Lead marked as unprocessed'})
            else:
                return Response(
                    {'error': 'Invalid action. Valid actions are: mark_processed, mark_unprocessed'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
        except ScrapingResult.DoesNotExist:
            return Response(
                {'error': 'Lead not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error updating lead: {str(e)}", exc_info=True)
            return Response(
                {'error': 'An error occurred while updating the lead'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class UserLeadsStatsAPIView(APIView):
    """
    API endpoint for user leads statistics
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        """Get lead statistics for the current user"""
        try:
            # Get all scraping jobs for the current user
            user_jobs = ScrapingJob.objects.filter(user=request.user)
            
            # Get all tasks related to these jobs
            tasks = ScrapingTask.objects.filter(job__in=user_jobs)
            
            # Get all leads
            leads = ScrapingResult.objects.filter(task__in=tasks)
            
            # Calculate statistics
            total_count = leads.count()
            processed_count = leads.filter(is_processed=True).count()
            unprocessed_count = total_count - processed_count
            duplicate_count = leads.filter(is_duplicate=True).count()
            
            # Calculate leads per day for the last 30 days
            timeline_data = []
            for i in range(30, -1, -1):
                date = timezone.now().date() - timezone.timedelta(days=i)
                count = leads.filter(created_at__date=date).count()
                timeline_data.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'count': count
                })
            
            # Calculate leads for the last week
            seven_days_ago = timezone.now() - timezone.timedelta(days=7)
            last_week_count = leads.filter(created_at__gte=seven_days_ago).count()
            
            # Return the statistics
            return Response({
                'total_count': total_count,
                'processed_count': processed_count,
                'unprocessed_count': unprocessed_count,
                'duplicate_count': duplicate_count,
                'last_week_count': last_week_count,
                'timeline': timeline_data
            })
            
        except Exception as e:
            logger.error(f"Error getting lead statistics: {str(e)}", exc_info=True)
            return Response(
                {'error': 'An error occurred while getting lead statistics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# Account Management API Views
class PasswordChangeAPIView(APIView):
    """
    API endpoint for changing user password
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        """Change user password"""
        try:
            # Get required fields
            current_password = request.data.get('current_password')
            new_password = request.data.get('new_password')
            re_new_password = request.data.get('re_new_password', new_password)
            
            # Validate input
            if not current_password or not new_password:
                return Response(
                    {'error': 'Current password and new password are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            if new_password != re_new_password:
                return Response(
                    {'error': 'New passwords do not match'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            # Validate minimum password requirements
            if len(new_password) < 8:
                return Response(
                    {'error': 'Password must be at least 8 characters long'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Verify current password
            user = request.user
            if not user.check_password(current_password):
                return Response(
                    {'error': 'Current password is incorrect'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            # Change password
            user.set_password(new_password)
            user.save()
            
            # Return success response
            return Response({
                'success': True,
                'message': 'Password changed successfully'
            })
            
        except Exception as e:
            logger.error(f"Error changing password: {str(e)}", exc_info=True)
            return Response(
                {'error': 'An error occurred while changing password'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AccountDeleteAPIView(APIView):
    """
    API endpoint for account deletion
    """
    permission_classes = [IsAuthenticated]
    
    def delete(self, request, *args, **kwargs):
        """Delete user account"""
        try:
            # Get password for confirmation
            current_password = request.data.get('current_password')
            
            # Validate input
            if not current_password:
                return Response(
                    {'error': 'Password confirmation is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            # Verify password
            user = request.user
            if not user.check_password(current_password):
                return Response(
                    {'error': 'Password is incorrect'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            # Get user email for logging
            user_email = user.email
                
            # Delete user account
            user.delete()
            
            # Log the deletion
            logger.info(f"User account deleted: {user_email}")
            
            # Return success response
            return Response(status=status.HTTP_204_NO_CONTENT)
            
        except Exception as e:
            logger.error(f"Error deleting account: {str(e)}", exc_info=True)
            return Response(
                {'error': 'An error occurred while deleting account'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UserSessionAPIView(APIView):
    """
    API endpoint for user session management
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        """Logout current session or all sessions"""
        try:
            action = request.data.get('action')
            
            if action == 'logout_all':
                # Get all outstanding tokens for the user
                tokens = OutstandingToken.objects.filter(user=request.user)
                
                # Blacklist all outstanding tokens
                for token in tokens:
                    BlacklistedToken.objects.get_or_create(token=token)
                
                return Response({
                    'success': True,
                    'message': 'All sessions have been logged out'
                })
                
            elif action == 'logout_current':
                # Get current token from request
                auth_header = request.headers.get('Authorization', '')
                if auth_header.startswith('Bearer '):
                    token = auth_header.split(' ')[1]
                    
                    # Blacklist the current token
                    try:
                        from rest_framework_simplejwt.tokens import TokenError
                        from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
                        from rest_framework_simplejwt.tokens import RefreshToken
                        
                        # Find the refresh token associated with this access token
                        # Since we only have the access token, we blacklist all refresh tokens
                        # for the current user as a security measure
                        for outstanding_token in OutstandingToken.objects.filter(user=request.user):
                            # Skip already blacklisted tokens
                            if not BlacklistedToken.objects.filter(token=outstanding_token).exists():
                                BlacklistedToken.objects.create(token=outstanding_token)
                    except Exception as token_error:
                        logger.warning(f"Could not blacklist token: {str(token_error)}")
                
                return Response({
                    'success': True,
                    'message': 'Current session has been logged out'
                })
                
            else:
                return Response(
                    {'error': 'Invalid action. Use "logout_all" or "logout_current"'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            logger.error(f"Error managing sessions: {str(e)}", exc_info=True)
            return Response(
                {'error': 'An error occurred while managing sessions'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class LeadAPIView(APIView):
    """
    API endpoint for listing and creating leads
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List leads for the current user"""
        try:
            # Get query parameters for filtering
            status = request.query_params.get('status')
            search = request.query_params.get('search')
            sort_by = request.query_params.get('sort_by', '-created_at')
            limit = int(request.query_params.get('limit', 50))
            offset = int(request.query_params.get('offset', 0))
            
            # Base queryset - only include leads owned by the current user
            queryset = Lead.objects.filter(user=request.user)
            
            # Apply status filter if provided
            if status:
                queryset = queryset.filter(status=status)
            
            # Apply search if provided
            if search:
                queryset = queryset.filter(
                    Q(name__icontains=search) | 
                    Q(email__icontains=search) | 
                    Q(company__icontains=search) |
                    Q(phone__icontains=search)
                )
            
            # Apply sorting
            if sort_by and sort_by in [
                'name', '-name', 'created_at', '-created_at', 'status', 
                '-status', 'priority', '-priority', 'last_contacted_at', '-last_contacted_at'
            ]:
                queryset = queryset.order_by(sort_by)
            else:
                queryset = queryset.order_by('-created_at')
            
            # Get total count
            total_count = queryset.count()
            
            # Get paginated results
            leads = queryset[offset:offset+limit]
            
            # Serialize the leads
            serializer = LeadSerializer(leads, many=True)
            
            # Return paginated response
            return Response({
                'results': serializer.data,
                'count': total_count,
                'offset': offset,
                'limit': limit
            })
            
        except Exception as e:
            logger.error(f"Error fetching leads: {str(e)}", exc_info=True)
            return Response(
                {'error': 'An error occurred while fetching leads'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self, request):
        """Create a new lead manually"""
        try:
            # Add the current user to the data
            data = request.data.copy()
            data['user'] = request.user.id
            
            # Validate and save the lead
            serializer = LeadSerializer(data=data)
            if serializer.is_valid():
                lead = serializer.save(user=request.user)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Error creating lead: {str(e)}", exc_info=True)
            return Response(
                {'error': 'An error occurred while creating the lead'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class LeadDetailAPIView(APIView):
    """
    API endpoint for retrieving, updating, and deleting a specific lead
    """
    permission_classes = [IsAuthenticated]
    
    def get_object(self, pk, user):
        try:
            return Lead.objects.get(pk=pk, user=user)
        except Lead.DoesNotExist:
            raise Http404
    
    def get(self, request, pk):
        """Get a specific lead by ID"""
        lead = self.get_object(pk, request.user)
        serializer = LeadSerializer(lead)
        return Response(serializer.data)
    
    def put(self, request, pk):
        """Update a specific lead by ID"""
        lead = self.get_object(pk, request.user)
        serializer = LeadSerializer(lead, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk):
        """Delete a specific lead by ID"""
        lead = self.get_object(pk, request.user)
        lead.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class LeadStatusUpdateAPIView(APIView):
    """
    API endpoint for bulk updating lead statuses
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Update the status of multiple leads at once"""
        try:
            lead_ids = request.data.get('lead_ids', [])
            new_status = request.data.get('status')
            
            if not lead_ids or not new_status:
                return Response(
                    {'error': 'lead_ids and status are required'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate the status
            valid_statuses = [status_choice[0] for status_choice in Lead.STATUS_CHOICES]
            if new_status not in valid_statuses:
                return Response(
                    {'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Update the leads that belong to the current user
            leads = Lead.objects.filter(id__in=lead_ids, user=request.user)
            
            # Update the status of all matching leads
            update_data = {'status': new_status}
            
            # If marking as contacted, update the last_contacted_at timestamp
            if new_status == 'contacted':
                update_data['last_contacted_at'] = timezone.now()
            
            updated_count = leads.update(**update_data)
            
            return Response({
                'updated_count': updated_count,
                'status': new_status
            })
            
        except Exception as e:
            logger.error(f"Error updating lead statuses: {str(e)}", exc_info=True)
            return Response(
                {'error': 'An error occurred while updating lead statuses'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class LeadStatsAPIView(APIView):
    """
    API endpoint for lead statistics
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get lead statistics for the current user"""
        try:
            # Get all leads for the current user
            leads = Lead.objects.filter(user=request.user)
            
            # Calculate basic stats
            total_leads = leads.count()
            
            # Get unique leads (not duplicates)
            unique_leads = total_leads
            
            # Get leads from last week
            last_week = timezone.now() - timedelta(days=7)
            last_week_leads = leads.filter(created_at__gte=last_week).count()
            
            # Calculate distribution by status
            status_distribution = {}
            for status_choice in Lead.STATUS_CHOICES:
                status_code = status_choice[0]
                status_distribution[status_choice[1]] = leads.filter(status=status_code).count()
            
            # Calculate timeline (leads per day for the last 30 days)
            timeline = {}
            
            # Get date 30 days ago
            start_date = (timezone.now() - timedelta(days=30)).date()
            end_date = timezone.now().date()
            
            # Create a list of all dates in range
            date_range = []
            current_date = start_date
            while current_date <= end_date:
                date_range.append(current_date)
                current_date = current_date + timedelta(days=1)
                
            # Get count for each date
            for date in date_range:
                next_date = date + timedelta(days=1)
                count = leads.filter(
                    created_at__gte=datetime.combine(date, datetime.min.time()),
                    created_at__lt=datetime.combine(next_date, datetime.min.time())
                ).count()
                
                # Format as ISO string for JS compatibility
                timeline[date.isoformat()] = count
            
            # Return stats
            return Response({
                'total': total_leads,
                'unique': unique_leads,
                'last_week': last_week_leads,
                'distribution': status_distribution,
                'timeline': timeline
            })
            
        except Exception as e:
            logger.error(f"Error getting lead statistics: {str(e)}", exc_info=True)
            return Response(
                {'error': 'An error occurred while getting lead statistics'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ScrapingJobDetailView(View):
    def get(self, request, job_id):
        try:
            # Check if user is authenticated
            if not request.user.is_authenticated:
                return JsonResponse({
                    'success': False,
                    'message': 'Authentication required'
                }, status=401)

            # Get the job and verify ownership
            try:
                job = ScrapingJob.objects.get(id=job_id, user=request.user)
            except ScrapingJob.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Job not found or access denied'
                }, status=404)

            # Get job details
            job_data = job.to_dict()
            
            # Add task information if available
            task = job.get_active_task()
            if task:
                job_data['task'] = {
                    'id': task.id,
                    'status': task.status,
                    'current_step': task.current_step,
                    'pages_explored': task.pages_explored,
                    'leads_found': task.leads_found,
                    'unique_leads': task.unique_leads,
                    'duration': task.duration
                }

            return JsonResponse({
                'success': True,
                'job': job_data
            })
        except Exception as e:
            import traceback
            logger.error(f"Error in ScrapingJobDetailView: {str(e)}\n{traceback.format_exc()}")
            return JsonResponse({'success': False, 'error': str(e)}, status=500)