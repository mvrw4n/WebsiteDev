import os
import json
import logging
import time
from django.conf import settings
from mistralai.client import MistralClient
from typing import List, Dict, Any, Optional
import sys
from .prompt_templates import SYSTEM_PROMPTS, SCRAPING_PROMPTS
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Add console handler with UTF-8 to avoid encoding errors
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Global variables for rate limiting
last_request_time = 0

class AIManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AIManager, cls).__new__(cls)
            cls._instance._init_clients()
        return cls._instance

    def _init_clients(self):
        """Initialize AI clients with API keys"""
        self.mistral_api_key = settings.MISTRAL_API_KEY
        self.mistral_client = MistralClient(api_key=self.mistral_api_key) if self.mistral_api_key else None
        self.mistral_config = settings.AI_CONFIG['mistral']
        self._validate_configuration()

    def _validate_configuration(self):
        """Validate that necessary configurations are present"""
        if not self.mistral_client:
            logger.error("❌ MistralAI client not initialized - missing API key")

    def send_mistral_request(self, messages, model=None, max_tokens=None, temperature=None):
        """
        Send a request to the Mistral API with JSON response format.
        Adds a pause if the last request was made less than a second ago.
        """
        global last_request_time

        if not self.mistral_api_key:
            logger.error("❌ Missing Mistral API key!")
            return {
                "message": "Configuration error: Missing Mistral API key",
                "response_chat": "Je suis désolé, il y a un problème avec la configuration du service IA. Veuillez contacter le support.",
                "actions_launched": "no_action",
                "error": "Missing API key"
            }

        # Use provided parameters or fallback to config
        model = model or self.mistral_config['default_model']
        max_tokens = max_tokens or self.mistral_config['max_tokens']
        temperature = temperature or self.mistral_config['temperature']

        # Check time elapsed since last request
        elapsed_time = time.time() - last_request_time
        min_delay = self.mistral_config.get('rate_limit', {}).get('min_delay_between_requests', 1.0)
        
        if elapsed_time < min_delay:
            sleep_time = min_delay - elapsed_time
            logger.info(f"⏳ Waiting {sleep_time:.2f} seconds to avoid too many requests.")
            time.sleep(sleep_time)

        try:
            # Send request via the official library
            logger.info(f"🔄 Sending request to Mistral API using model: {model}")
            
            # Log the messages being sent (for debugging)
            for idx, msg in enumerate(messages):
                logger.debug(f"Message {idx} - {msg['role']}: {msg['content'][:100]}...")
                
            chat_response = self.mistral_client.chat(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                response_format={"type": "json_object"}
            )

            # Update last request time
            last_request_time = time.time()

            # Debug the response
            logger.info(f"🔵 Mistral Response received")
            
            # Check response format
            if chat_response.choices and len(chat_response.choices) > 0:
                json_response = chat_response.choices[0].message.content.strip()
                
                # Log the raw response for debugging
                logger.debug(f"Raw Mistral content: {json_response}")

                # Check if json_response is already a dictionary
                if isinstance(json_response, str):
                    try:
                        # Simple case - try to parse the JSON directly first
                        try:
                            parsed_json = json.loads(json_response)
                            return parsed_json
                        except json.JSONDecodeError:
                            # If direct parsing fails, try to fix common issues
                            logger.warning("JSON parsing failed on first attempt, trying to fix response")
                        
                        # Try to safely parse the JSON, handling potential truncation
                        # Sometimes the response might be truncated due to token limits
                        json_response = json_response.rstrip(',')  # Remove trailing commas
                        
                        # Handle common truncation patterns
                        if json_response.endswith('"'):  # Incomplete string
                            json_response += '"}'  # Close the string and object
                        
                        # Check for unmatched brackets
                        open_braces = json_response.count('{')
                        close_braces = json_response.count('}')
                        if open_braces > close_braces:
                            # Add missing closing braces
                            json_response += '}' * (open_braces - close_braces)
                            
                        # Try to parse the fixed JSON
                        try:
                            parsed_json = json.loads(json_response)
                            logger.info("Successfully parsed JSON after fixing format issues")
                            return parsed_json
                        except json.JSONDecodeError as e:
                            # If still fails, try more aggressive fix
                            logger.warning(f"Second JSON parsing attempt failed: {e}")
                            
                            # Find the last valid position of JSON
                            for i in range(len(json_response) - 1, 0, -1):
                                try:
                                    test_json = json_response[:i] + "}"
                                    parsed_json = json.loads(test_json)
                                    logger.info("Successfully recovered truncated JSON")
                                    return parsed_json
                                except:
                                    continue
                            
                            # If all parsing attempts fail, try to extract just the "response_chat" part
                            # This is a last resort to at least show something to the user
                            try:
                                # Look for "response_chat": "some text" pattern
                                match = re.search(r'"response_chat"\s*:\s*"([^"]+)"', json_response)
                                if match:
                                    response_text = match.group(1)
                                    logger.info(f"Extracted response_chat text: {response_text[:50]}...")
                                    return {
                                        "message": response_text,
                                        "response_chat": response_text,
                                        "actions_launched": "no_action",
                                        "parsing_error": True
                                    }
                            except Exception as ex:
                                logger.error(f"Failed to extract response_chat: {ex}")
                            
                            logger.error(f"❌ Could not parse Mistral response as JSON after recovery attempts")
                            
                            # Return a friendly error message to the user
                            return {
                                "message": "Je suis désolé, j'ai eu un problème technique avec ma réponse.",
                                "response_chat": "Je suis désolé, j'ai rencontré un problème technique dans le traitement de votre demande. Pourriez-vous reformuler ou essayer une autre question ?",
                                "actions_launched": "no_action",
                                "error": f"JSON parsing error: {str(e)}"
                            }
                    except json.JSONDecodeError as e:
                        logger.error(f"❌ Could not parse Mistral response as JSON: {json_response[:200]}...")
                        logger.error(f"JSONDecodeError: {str(e)}")
                        # Return a basic response structure
                        return {
                            "message": "Je suis désolé, j'ai rencontré une erreur dans le traitement de la réponse.",
                            "response_chat": "Je suis désolé, j'ai rencontré une erreur dans le traitement de la réponse. Veuillez réessayer votre demande avec des termes différents.",
                            "actions_launched": "no_action",
                            "error": f"JSON parsing error: {str(e)}"
                        }
                elif isinstance(json_response, dict):
                    return json_response  # If it's already a dictionary, return it directly
                else:
                    logger.error(f"❌ Unexpected format of Mistral response: {type(json_response)}")
                    return {
                        "message": "Erreur de format dans la réponse.",
                        "response_chat": "Je suis désolé, j'ai rencontré une erreur dans le format de la réponse. Veuillez réessayer avec une question plus simple.",
                        "actions_launched": "no_action",
                        "error": f"Unexpected response format: {type(json_response)}"
                    }
            else:
                logger.error("❌ Mistral returned an empty or malformed response.")
                return {
                    "message": "Réponse vide ou mal formatée.",
                    "response_chat": "Je suis désolé, j'ai reçu une réponse vide ou mal formatée. Le service IA semble avoir des problèmes temporaires. Veuillez réessayer plus tard.",
                    "actions_launched": "no_action",
                    "error": "Empty or malformed response"
                }

        except Exception as e:
            logger.error(f"🚨 Error in Mistral API call: {str(e)}")
            # Include traceback for debugging
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            return {
                "message": f"Erreur lors de la communication avec Mistral AI",
                "response_chat": "Je suis désolé, une erreur est survenue lors de la communication avec le service IA. Veuillez réessayer dans quelques instants ou contacter le support si le problème persiste.",
                "actions_launched": "no_action",
                "error": f"API error: {str(e)}"
            }

    async def analyze_user_message(self, message: str, user_context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Analyze user message and determine appropriate action and response.
        """
        language = 'fr'  # Default language
        if user_context:
            language = user_context.get('language', settings.LANGUAGE_SETTINGS['default'])
            
        try:
            # Prepare the system message with available actions and context
            system_message = self._build_system_message(user_context)
            
            # Prepare the messages for the AI
            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": message}
            ]
            
            logger.info(f"Sending message to Mistral: {message[:50]}...")

            # Determine if we should use the large model based on message complexity
            complex_indicators = [
                'structure', 'scraping', 'extraire', 'analyser', 'complexe', 'données', 
                'stratégie', 'avancé', 'specifique', 'détaillé', 'intelligence'
            ]
            message_complexity = sum(1 for indicator in complex_indicators if indicator in message.lower())
            use_large_model = message_complexity >= 2 or len(message.split()) > 25
            
            model_to_use = "mistral-large-latest" if use_large_model else None
            logger.info(f"Complexity assessment: {message_complexity}/10, using model: {model_to_use or 'default'}")

            # Use send_mistral_request with model choice based on complexity
            response_data = self.send_mistral_request(messages, model=model_to_use)

            # Validate response
            if not response_data:
                logger.error("Empty response from Mistral")
                return {
                    "message": settings.LANGUAGE_SETTINGS['responses'][language]['error'],
                    "response_chat": settings.LANGUAGE_SETTINGS['responses'][language]['error'],
                    "actions_launched": "no_action",
                    "error": "Empty response from Mistral"
                }

            # Make sure message field exists
            if "message" not in response_data:
                logger.warning("Response missing 'message' field")
                response_data["message"] = settings.LANGUAGE_SETTINGS['responses'][language]['default_response']
                response_data["response_chat"] = response_data["message"]
            
            # Ensure response_chat field exists
            if "response_chat" not in response_data:
                response_data["response_chat"] = response_data["message"]
                
            # Ensure actions_launched field exists
            if "actions_launched" not in response_data:
                if "action" in response_data and "type" in response_data["action"]:
                    response_data["actions_launched"] = response_data["action"]["type"]
                else:
                    response_data["actions_launched"] = "no_action"
            
            # Validate and fix structure if needed
            valid_structure = self._validate_response_structure(response_data)
            if not valid_structure:
                logger.warning("Invalid response structure, using default response")
                response_data = {
                    "message": settings.LANGUAGE_SETTINGS['responses'][language]['default_response'],
                    "response_chat": settings.LANGUAGE_SETTINGS['responses'][language]['default_response'],
                    "actions_launched": "no_action"
                }
            
            # Detect structure information from the message and response
            self._detect_and_enrich_scraping_structure(message, response_data)
            
            # If an action is present, process it
            if 'action' in response_data:
                logger.info(f"Processing action: {response_data['action'].get('type')}")
                action_response = await self.process_action(
                    response_data['action']['type'],
                    response_data['action'].get('parameters', {}),
                    language
                )
                response_data.update(action_response)
            
            # Ensure the response is properly formatted before returning
            if 'structure_update' in response_data:
                logger.info(f"Structure update present in response: {response_data['structure_update'].get('name', 'Unnamed')}")
                response_data['actions_launched'] = 'update_structure'
            
            return response_data

        except Exception as e:
            logger.error(f"🚨 Error in analyze_user_message: {str(e)}", exc_info=True)
            return {
                "message": settings.LANGUAGE_SETTINGS['responses'][language]['error'],
                "response_chat": settings.LANGUAGE_SETTINGS['responses'][language]['error'],
                "actions_launched": "no_action",
                "error": str(e)
            }

    def _build_system_message(self, user_context: Optional[Dict] = None) -> str:
        """Build the system message including available actions and context"""
        # Determine which prompt to use based on user_context
        use_gdpr_compliance = False
        if user_context and 'use_gdpr_compliance' in user_context:
            use_gdpr_compliance = user_context.get('use_gdpr_compliance', False)
        
        # Select the appropriate prompt template
        if use_gdpr_compliance:
            logger.info("Using GDPR-compliant chat assistant prompt")
            base_message = SYSTEM_PROMPTS['chat_assistant_gdpr_compliant']
        else:
            logger.info("Using standard permissive chat assistant prompt")
            base_message = SYSTEM_PROMPTS['chat_assistant_permissive']
        
        # Add available templates
        base_message += "\nAvailable Data Structures:\n"
        for template_name, template_data in settings.SCRAPING_TEMPLATES.items():
            base_message += f"- {template_name}: {json.dumps(template_data['structure'], indent=2)}\n"

        # Add user context if provided
        if user_context:
            # Create a copy of user_context to avoid modifying the original
            context_to_add = user_context.copy()
            # Remove the use_gdpr_compliance flag from what we send to the AI
            if 'use_gdpr_compliance' in context_to_add:
                del context_to_add['use_gdpr_compliance']
            
            if context_to_add:  # Only add if there's still context after removing the flag
                base_message += f"\nUser Context:\n{json.dumps(context_to_add, indent=2)}"

        return base_message

    def _validate_response_structure(self, response: Dict) -> bool:
        """
        Validate that the response has the required structure and fix if possible.
        Returns True if valid, False if couldn't be fixed.
        """
        # Check if message exists
        if "message" not in response:
            return False
            
        # If action is present, validate its structure
        if "action" in response:
            # Make sure action is a dict
            if not isinstance(response["action"], dict):
                response["action"] = {"type": "unknown"}
                return False
                
            # Make sure type is present
            if "type" not in response["action"]:
                response["action"]["type"] = "unknown"
                return False
                
            # Check for valid action type
            valid_types = [action[0] for action in settings.AI_ACTION_TYPES]
            if response["action"]["type"] not in valid_types:
                # Default to a safe action type
                response["action"]["type"] = "serp_scraping"
                
            # Ensure parameters exist
            if "parameters" not in response["action"]:
                response["action"]["parameters"] = {}
        
        return True

    @staticmethod
    def get_template_structure(template_name: str) -> Dict:
        """Get the structure for a specific template"""
        return settings.SCRAPING_TEMPLATES.get(template_name, {}).get('structure', {})

    def get_response_template(self, action_type: str, key: str, language: str = 'fr', **kwargs) -> str:
        """Get a response template for a specific action type and language"""
        try:
            template = settings.AI_RESPONSE_TEMPLATES[action_type][language][key]
            return template.format(**kwargs)
        except (KeyError, ValueError):
            return settings.LANGUAGE_SETTINGS['responses'][language]['error']

    async def handle_serp_scraping(self, parameters: Dict, language: str = 'fr') -> Dict:
        """Handle SERP scraping action"""
        try:
            query = parameters.get('query')
            if not query:
                raise ValueError("Query parameter is required for SERP scraping")

            # Return initial response while the scraping is queued
            return {
                "message": self.get_response_template('serp_scraping', 'start', language, query=query),
                "action": {
                    "type": "serp_scraping",
                    "parameters": parameters,
                    "status": "queued"
                }
            }
        except Exception as e:
            logger.error(f"Error in handle_serp_scraping: {str(e)}", exc_info=True)
            return {
                "message": self.get_response_template('serp_scraping', 'error', language),
                "error": str(e)
            }

    async def handle_linkedin_scraping(self, parameters: Dict, language: str = 'fr') -> Dict:
        """Handle LinkedIn scraping action"""
        try:
            # Return initial response while the scraping is queued
            return {
                "message": self.get_response_template('linkedin_scraping', 'start', language),
                "action": {
                    "type": "linkedin_scraping",
                    "parameters": parameters,
                    "status": "queued"
                }
            }
        except Exception as e:
            logger.error(f"Error in handle_linkedin_scraping: {str(e)}", exc_info=True)
            return {
                "message": self.get_response_template('linkedin_scraping', 'error', language),
                "error": str(e)
            }

    async def process_action(self, action_type: str, parameters: Dict, language: str = 'fr') -> Dict:
        """Process an action based on its type"""
        action_handlers = {
            'serp_scraping': self.handle_serp_scraping,
            'linkedin_scraping': self.handle_linkedin_scraping,
        }

        handler = action_handlers.get(action_type)
        if not handler:
            return {
                "message": settings.LANGUAGE_SETTINGS['responses'][language]['error'],
                "error": f"Unsupported action type: {action_type}"
            }

        return await handler(parameters, language)

    # Utility functions for scraping (to be implemented)
    
    def analyze_serp_results(self, serp_results, json_structure):
        """
        Analyze SERP results to extract the official site and relevant links.
        """
        try:
            # Prepare the prompt using the template
            try:
                # Protection supplémentaire contre les erreurs de formatage
                template = SCRAPING_PROMPTS.get('serp_analysis', '')
                if not template:
                    logger.error("Template 'serp_analysis' not found in SCRAPING_PROMPTS")
                    return {"official_website": "", "priority_links": []}
                    
                prompt = template.format(
                    serp_results=json.dumps(serp_results, indent=2),
                    json_structure=json.dumps(json_structure, indent=2)
                )
            except KeyError as ke:
                logger.error(f"KeyError while accessing serp_analysis template: {str(ke)}")
                return {"official_website": "", "priority_links": []}
            except Exception as fe:
                logger.error(f"Formatting error with serp_analysis template: {str(fe)}")
                return {"official_website": "", "priority_links": []}
            
            # Protection contre les résultats SERP vides
            if not serp_results or len(serp_results) == 0:
                logger.warning("Empty SERP results, returning default response")
                return {"official_website": "", "priority_links": []}
            
            # Create a message for the AI
            messages = [
                {"role": "system", "content": "You are a web scraping expert selecting official sites and relevant links."},
                {"role": "user", "content": prompt}
            ]
            
            # --- DEBUG: Log the final prompt being sent ---
            logger.debug("--- PROMPT POUR ANALYSE SERP ---")
            logger.debug(f"System: {messages[0]['content']}")
            logger.debug(f"User: {messages[1]['content']}") # Log the full user prompt
            logger.debug("---------------------------------")
            # --- END DEBUG ---

            # Send the request to Mistral - explicitly use the large model for complex analysis
            result = self.send_mistral_request(messages, model="mistral-large-latest")
            
            if not isinstance(result, dict):
                logger.error(f"❌ Invalid response from Mistral: {result}")
                return {"official_website": "", "priority_links": []}
            
            # Validate expected fields
            if "official_website" not in result or "priority_links" not in result:
                logger.error(f"❌ Missing required fields in Mistral response: {result}")
                default_result = {"official_website": "", "priority_links": []}
                # Try to salvage any existing valid fields
                if isinstance(result.get("official_website"), str):
                    default_result["official_website"] = result["official_website"]
                if isinstance(result.get("priority_links"), list):
                    default_result["priority_links"] = result["priority_links"]
                result = default_result
            
            logger.info(f"✅ SERP Analysis Result: {json.dumps(result, indent=2)}")
            return result
            
        except Exception as e:
            logger.error(f"Error in analyze_serp_results: {str(e)}", exc_info=True)
            return {"official_website": "", "priority_links": []}

    def analyze_html_content(self, html_content, objective, json_structure, structure_schema=None):
        """
        Analyze HTML content to extract structured data according to the provided template.
        
        Args:
            html_content (str): HTML content to analyze
            objective (str): Extraction objective
            json_structure (dict): Base JSON structure
            structure_schema (list, optional): Custom structure schema defining fields
            
        Returns:
            dict: Extracted data in structured format
        """
        try:
            # Limit HTML content length to prevent token overflow
            html_content_truncated = html_content[:12000] if html_content else ""
            
            if not html_content_truncated:
                logger.warning("Empty HTML content provided to analyze_html_content")
                return {"contacts": [], "tenders": []} if not structure_schema else {}
            
            # Check for custom structure schema
            custom_structure_guidance = ""
            response_template = {}
            
            if structure_schema:
                # Create a template based on the schema
                for field in structure_schema:
                    field_name = field.get('name')
                    field_type = field.get('type', 'text')
                    
                    # Set default value based on type
                    if field_type == 'number':
                        response_template[field_name] = 0
                    else:
                        response_template[field_name] = ""
                
                # Extract required fields for emphasis
                required_fields = [field.get('name') for field in structure_schema if field.get('required', False)]
                
                # Create an example based on the schema with realistic values
                example_structure = {}
                for field in structure_schema:
                    field_name = field.get('name')
                    field_type = field.get('type', 'text')
                    
                    # Add appropriate example values based on field name and type
                    if field_type == 'number':
                        example_structure[field_name] = 42
                    elif field_type == 'email':
                        example_structure[field_name] = "contact@example.com"
                    elif field_type == 'url' or field_name.endswith('_web') or field_name.endswith('website') or 'site_web' in field_name:
                        example_structure[field_name] = "https://www.example.com"
                    elif field_name.startswith('linkedin') or 'linkedin' in field_name:
                        example_structure[field_name] = "https://www.linkedin.com/company/example"
                    elif field_name.startswith('twitter') or 'twitter' in field_name:
                        example_structure[field_name] = "https://twitter.com/example"
                    elif 'description' in field_name or 'about' in field_name:
                        example_structure[field_name] = "This is a company that specializes in software development."
                    elif 'nom_entreprise' in field_name or 'company' in field_name or 'entreprise' in field_name:
                        example_structure[field_name] = "Example Company, Inc."
                    elif 'secteur' in field_name or 'industry' in field_name or 'activite' in field_name:
                        example_structure[field_name] = "Technology"
                    elif 'taille' in field_name or 'size' in field_name:
                        example_structure[field_name] = "50-200 employees"
                    elif 'contact' in field_name and ('nom' in field_name or 'name' in field_name):
                        example_structure[field_name] = "John Doe"
                    elif 'fonction' in field_name or 'titre' in field_name or 'position' in field_name:
                        example_structure[field_name] = "Chief Technology Officer"
                    elif 'telephone' in field_name or 'phone' in field_name:
                        example_structure[field_name] = "+1 (555) 123-4567"
                    else:
                        example_structure[field_name] = f"Example value for {field_name}"
                
                # Create field mapping guidance to help the AI understand field names
                field_mappings = {
                    "name": ["nom", "name", "contact_name", "nom_contact"],
                    "company": ["nom_entreprise", "entreprise", "company", "société", "organization"],
                    "website": ["site_web", "website", "url", "site_internet"],
                    "industry": ["secteur_activite", "industry", "sector", "domaine"],
                    "size": ["taille_entreprise", "size", "employees", "effectif"],
                    "description": ["description", "about", "a_propos", "presentation"],
                    "email": ["email", "courriel", "mail", "email_contact"],
                    "phone": ["telephone", "phone", "tel", "telephone_contact"],
                    "position": ["fonction", "position", "titre", "title", "titre_contact"],
                    "linkedin": ["linkedin", "linkedin_url", "linkedin_profile"],
                    "twitter": ["twitter", "twitter_url", "twitter_profile"]
                }
                
                # Build custom structure guidance
                custom_structure_guidance = f"""
CUSTOM STRUCTURE EXTRACTION:
You MUST return data in this EXACT format with these EXACT field names:
```json
{json.dumps(example_structure, indent=2)}
```

FIELD REQUIREMENTS:
- Required fields that MUST be included: {', '.join(required_fields)}
- All field names MUST be spelled EXACTLY as shown above
- Do NOT add any fields not in the schema
- For fields not found in the HTML, use empty strings or 0 for numbers

FIELD NAME MAPPING GUIDE:
- Name/contact fields: use '{next((f for f in structure_schema if f.get('name') in field_mappings["name"]), {}).get('name', '')}'
- Company name: use '{next((f for f in structure_schema if f.get('name') in field_mappings["company"]), {}).get('name', '')}'
- Website: use '{next((f for f in structure_schema if f.get('name') in field_mappings["website"]), {}).get('name', '')}'
- Industry fields: use '{next((f for f in structure_schema if f.get('name') in field_mappings["industry"]), {}).get('name', '')}'
- Size fields: use '{next((f for f in structure_schema if f.get('name') in field_mappings["size"]), {}).get('name', '')}'
- Description fields: use '{next((f for f in structure_schema if f.get('name') in field_mappings["description"]), {}).get('name', '')}'
- Email fields: use '{next((f for f in structure_schema if f.get('name') in field_mappings["email"]), {}).get('name', '')}'
- Phone fields: use '{next((f for f in structure_schema if f.get('name') in field_mappings["phone"]), {}).get('name', '')}'
- Position fields: use '{next((f for f in structure_schema if f.get('name') in field_mappings["position"]), {}).get('name', '')}'

SPECIAL INSTRUCTIONS FOR INDUSTRY/SECTOR:
- For '{next((f for f in structure_schema if f.get('name') in field_mappings["industry"]), {}).get('name', 'secteur_activite')}', you MUST make a best effort to identify the company's industry
- Look for keywords in the description, text, meta tags, and navigation menu
- If industry isn't explicitly stated, infer it from:
  * Company description
  * Products/services mentioned
  * Case studies
  * Client types
  * Messaging/terminology used
- Always provide a value - never leave it empty if the field is required
- Use broad categories like "Technology", "Manufacturing", "Healthcare", "Finance", "Education", "Retail", "Media", etc.
- If you're unsure but can make an educated guess, add "Probable: " prefix (e.g., "Probable: Technology Services")

IMPORTANT: Return ONLY a valid JSON object with NO explanations, and EXACTLY the field names shown above.
"""
            
            # Prepare the prompt - either with standard template or custom structure
            if structure_schema:
                # Custom prompt for structure schema
                prompt = f"""
You are an expert in extracting structured data from HTML content.

OBJECTIVE: {objective}

{custom_structure_guidance}

HTML CONTENT TO ANALYZE:
{html_content_truncated}

CRITICAL REQUIREMENTS:
1. Return data in the EXACT format shown above with EXACT field names
2. Return ONLY a valid JSON object with NO explanations or formatting
3. Do NOT use markdown code blocks
4. Include ALL fields from the schema with at least empty values if not found
"""
            else:
                # Use the standard prompt template
                try:
                    template = SCRAPING_PROMPTS.get('html_extraction', '')
                    if not template:
                        logger.error("Template 'html_extraction' not found in SCRAPING_PROMPTS")
                        return {"contacts": [], "tenders": []}
                        
                    prompt = template.format(
                        objective=objective,
                        json_structure=json.dumps(json_structure, indent=2),
                        html_content=html_content_truncated
                    )
                except KeyError as ke:
                    logger.error(f"KeyError while accessing html_extraction template: {str(ke)}")
                    return json_structure # Return original structure instead of empty
                except Exception as fe:
                    logger.error(f"Formatting error with html_extraction template: {str(fe)}")
                    return json_structure # Return original structure instead of empty
            
            # Create a message for the AI
            messages = [
                {"role": "system", "content": "You are an expert in extracting structured data from HTML. Return ONLY valid JSON with no explanations."},
                {"role": "user", "content": prompt}
            ]

            # --- DEBUG: Log the final prompt being sent ---
            logger.debug("--- PROMPT POUR EXTRACTION HTML ---")
            logger.debug(f"System: {messages[0]['content']}")
            logger.debug(f"User: {messages[1]['content']}") # Log the full user prompt
            logger.debug("----------------------------------")
            # --- END DEBUG ---

            # Send the request to Mistral - explicitly use the large model for complex extraction
            result = self.send_mistral_request(messages, model="mistral-large-latest")
            
            if not isinstance(result, dict):
                logger.error(f"❌ Could not retrieve a valid JSON from Mistral: {result}")
                # Try to extract JSON from the response text if it's a string
                if isinstance(result, str):
                    json_str = self._extract_json_from_text(result)
                    if json_str:
                        try:
                            result = json.loads(json_str)
                        except json.JSONDecodeError:
                            logger.error("Failed to parse extracted JSON string")
                            return structure_schema and response_template or json_structure
                else:
                    return structure_schema and response_template or json_structure
            
            # Validate the results depending on structure type
            if structure_schema:
                # For custom structure schema, validate required fields
                missing_fields = []
                for field in structure_schema:
                    field_name = field.get('name')
                    is_required = field.get('required', False)
                    
                    if is_required and (field_name not in result or result[field_name] is None or 
                                        (isinstance(result[field_name], str) and not result[field_name].strip())):
                        missing_fields.append(field_name)
                        # Add default values for missing fields
                        if field.get('type') == 'number':
                            result[field_name] = 0
                        else:
                            result[field_name] = ""
                
                if missing_fields:
                    logger.warning(f"❌ Missing required fields in result: {', '.join(missing_fields)}")
                
                # Remove fields not in the schema
                schema_fields = [field.get('name') for field in structure_schema]
                extra_fields = [field for field in list(result.keys()) if field not in schema_fields]
                
                for field in extra_fields:
                    logger.warning(f"⚠️ Removing extra field from result: {field}")
                    del result[field]
                
                logger.info(f"✅ Custom structure extraction complete with fields: {list(result.keys())}")
                return result
            
            else:
                # For standard structure, validate against original keys
                if not all(key in result for key in json_structure.keys()):
                    logger.warning("Missing keys in result compared to original structure. Merging with original.")
                    # Create a merged structure with original fields and any new data
                    merged_result = json_structure.copy()
                    
                    # Add new contacts if found
                    if "contacts" in result and isinstance(result["contacts"], list):
                        if "contacts" not in merged_result:
                            merged_result["contacts"] = []
                        merged_result["contacts"].extend(result["contacts"])
                    
                    result = merged_result
                
                logger.info(f"✅ HTML Extraction Result Structure: {list(result.keys())}")
                return result
            
        except Exception as e:
            logger.error(f"Error in analyze_html_content: {str(e)}", exc_info=True)
            # Return template or original structure
            return structure_schema and response_template or json_structure

    def generate_search_variations(self, prompt):
        """Generate variations of search queries based on a primary query"""
        messages = [
            {"role": "system", "content": "Tu es un assistant spécialisé dans la génération de requêtes de recherche pertinentes pour trouver des informations commerciales et des contacts."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            # Get query variations from Mistral API
            result = self.send_mistral_request(messages)
            
            # Parse the result and ensure it's correctly formatted
            if isinstance(result, list):
                # Return the list directly
                return result
            
            # Try to extract JSON array from text response
            json_str = self._extract_json_from_text(result)
            if json_str:
                try:
                    parsed = json.loads(json_str)
                    if isinstance(parsed, list):
                        return parsed
                    elif isinstance(parsed, dict) and "queries" in parsed:
                        return parsed["queries"]
                except:
                    pass
                
            # If not a JSON or list, try to extract by line 
            lines = result.strip().split('\n')
            clean_lines = []
            for line in lines:
                # Clean up typical formatting like "1. Query" or "- Query"
                clean_line = re.sub(r'^[\d\-\.\*\s]+', '', line).strip()
                if clean_line and len(clean_line) > 5:  # Only include non-empty queries
                    clean_lines.append(clean_line)
            
            return clean_lines
            
        except Exception as e:
            logger.error(f"Error generating search variations: {str(e)}", exc_info=True)
            return []

    def _extract_json_from_text(self, text):
        """Extract JSON object from text that might contain explanations or other content"""
        if not text or not isinstance(text, str):
            return None
            
        # First try to find JSON with pattern matching
        json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        match = re.search(json_pattern, text)
        if match:
            return match.group(1).strip()
            
        # If no JSON block found, try to extract anything between { and } with balanced brackets
        try:
            # Find the position of the first {
            start_pos = text.find('{')
            if start_pos >= 0:
                # Keep track of opening and closing brackets
                open_brackets = 1
                for i in range(start_pos + 1, len(text)):
                    if text[i] == '{':
                        open_brackets += 1
                    elif text[i] == '}':
                        open_brackets -= 1
                        
                    if open_brackets == 0:
                        # Found the matching closing bracket
                        return text[start_pos:i+1]
        except Exception:
            pass
            
        return None 

    def determine_next_action(self, prompt):
        """Determine the next action based on page content and links"""
        messages = [
            {"role": "system", "content": "Tu es un assistant spécialisé en navigation web intelligente pour extraire des informations."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            # Get analysis from Mistral API 
            action_result = self.send_mistral_request(messages)
            
            # Parse the result and ensure it's correctly formatted
            if isinstance(action_result, dict):
                # Return the structured data 
                return action_result
            else:
                # Try to extract JSON from text response
                json_str = self._extract_json_from_text(action_result)
                if json_str:
                    return json.loads(json_str)
                
                # Fallback with go_next_page
                logger.warning("No valid JSON found in next action response")
                return {"action": "go_next_page"}
                
        except Exception as e:
            logger.error(f"Error determining next action: {str(e)}", exc_info=True)
            # Return default action in case of error
            return {"action": "go_next_page"} 

    def _detect_and_enrich_scraping_structure(self, message, response_data):
        """
        Detects and enriches scraping structure from user message
        
        This is a backward compatibility method to ensure older code paths
        still work even if they call this method. It's a no-op now
        but prevents AttributeError when called from other modules.
        
        Args:
            message (str): The user message
            response_data (dict): The response data dictionary to enrich
            
        Returns:
            None - modifies response_data in place if needed
        """
        # This is intentionally a no-op to maintain compatibility
        # with existing code that might call this method
        logger.info("_detect_and_enrich_scraping_structure called (compatibility method)")
        
        # Make sure response_data has required fields to avoid errors
        if 'actions_launched' not in response_data:
            response_data['actions_launched'] = []
            
        return 