import json
import logging
import time
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Retrieve API keys from settings
OPENAI_API_KEY = settings.OPENAI_API_KEY
MISTRAL_API_KEY = getattr(settings, 'MISTRAL_API_KEY', '')

# OpenAI API configuration
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_HEADERS = {
    "Authorization": f"Bearer {OPENAI_API_KEY}",
    "Content-Type": "application/json"
}

# Rate limiting
last_api_call_time = 0
MIN_DELAY_BETWEEN_CALLS = 1.5  # seconds

def enforce_rate_limit():
    """Enforce rate limiting between API calls"""
    global last_api_call_time
    current_time = time.time()
    elapsed = current_time - last_api_call_time
    
    if elapsed < MIN_DELAY_BETWEEN_CALLS:
        sleep_time = MIN_DELAY_BETWEEN_CALLS - elapsed
        logger.info(f"Rate limiting: Sleeping for {sleep_time:.2f} seconds")
        time.sleep(sleep_time)
    
    last_api_call_time = time.time()

def send_openai_request(messages, model="gpt-4o", max_tokens=2000, temperature=0.7):
    """
    Send a request to the OpenAI API with the provided messages.
    
    Args:
        messages (list): List of message objects (role, content)
        model (str): Model to use
        max_tokens (int): Maximum tokens in response
        temperature (float): Temperature for response generation
        
    Returns:
        str or None: API response or None if failed
    """
    if not OPENAI_API_KEY:
        logger.error("OpenAI API key is missing")
        return None
        
    enforce_rate_limit()
    
    data = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature
    }

    try:
        response = requests.post(OPENAI_API_URL, headers=OPENAI_HEADERS, json=data, timeout=30)
        response.raise_for_status()
        
        response_json = response.json()
        
        if "choices" in response_json and len(response_json["choices"]) > 0:
            return response_json["choices"][0]["message"]["content"].strip()
        else:
            logger.error(f"OpenAI returned an invalid response: {response_json}")
            return None

    except requests.exceptions.RequestException as e:
        logger.error(f"Error during OpenAI API call: {str(e)}")
        return None

def analyze_html_with_gpt(html_content, objective, json_structure, structure_schema=None):
    """
    Analyze HTML content using GPT to extract structured information.
    
    Args:
        html_content (str): Formatted HTML content
        objective (str): Scraping objective
        json_structure (dict): Current JSON structure
        structure_schema (list, optional): Schema defining what fields to extract
        
    Returns:
        dict: Updated JSON structure with extracted data
    """
    if not html_content or len(html_content.strip()) < 100:
        logger.warning("HTML content too short for analysis")
        return json_structure
    
    # Log the structure schema for debugging
    if structure_schema:
        required_fields = [field.get('name') for field in structure_schema if field.get('required', False)]
        logger.debug(f"Structure schema has {len(structure_schema)} fields, with required fields: {', '.join(required_fields)}")
    else:
        logger.debug("No structure schema provided")
        
    # Truncate HTML content if it's too long
    truncated_html = html_content[:15000] if len(html_content) > 15000 else html_content
    
    # If using a custom schema, we need to create a response template that follows the schema
    response_template = {}
    structure_guidance = ""
    
    if structure_schema:
        # Create field mappings from common field names to structure field names
        field_mappings = {
            "name": ["nom", "name", "contact_name", "company_name", "nom_contact", "nom_entreprise"],
            "email": ["email", "courriel", "mail", "email_contact"],
            "phone": ["telephone", "phone", "tel", "telephone_contact", "mobile"],
            "company": ["entreprise", "company", "société", "organization", "nom_entreprise"],
            "position": ["fonction", "position", "titre", "title", "titre_contact"],
            "website": ["site_web", "website", "url", "site_internet"],
            "industry": ["secteur_activite", "industry", "sector", "domaine"],
            "size": ["taille_entreprise", "size", "employees", "effectif"],
            "description": ["description", "about", "a_propos", "presentation"],
            "linkedin": ["linkedin", "linkedin_url", "linkedin_profile"],
            "twitter": ["twitter", "twitter_url", "twitter_profile", "x_profile"]
        }
        
        # Create a dictionary to map common field names to structure field names
        exact_field_mapping = {}
        for field in structure_schema:
            field_name = field.get('name')
            # Find which common field this might correspond to
            for common_field, aliases in field_mappings.items():
                if field_name in aliases:
                    exact_field_mapping[common_field] = field_name
                    break
        
        # Create a custom JSON object following the structure schema
        for field in structure_schema:
            field_name = field.get('name')
            field_type = field.get('type', 'text')
            is_required = field.get('required', False)
            
            # Set default value based on type
            default_value = None
            if field_type == 'number':
                default_value = 0
            elif field_type in ['url', 'email', 'text']:
                default_value = ""
            
            # Create the field in the template
            response_template[field_name] = default_value
        
        # Extract required field names for emphasis
        required_fields = [field.get('name') for field in structure_schema if field.get('required', False)]
        required_fields_str = ", ".join(required_fields)
        
        # Build a complete example structure with all fields as an example
        example_structure = {}
        field_descriptions = {}
        
        for field in structure_schema:
            field_name = field.get('name')
            field_type = field.get('type', 'text')
            field_desc = field.get('description', 'No description available')
            field_descriptions[field_name] = field_desc
            
            # Create example value based on field type and name
            if field_type == 'number':
                example_structure[field_name] = 42
            elif field_type == 'email':
                example_structure[field_name] = "contact@example.com"
            elif field_type == 'url' or field_name.endswith('_web') or field_name.endswith('website'):
                example_structure[field_name] = "https://www.example.com"
            elif field_name.startswith('linkedin') or 'linkedin' in field_name:
                example_structure[field_name] = "https://www.linkedin.com/company/example"
            elif field_name.startswith('twitter') or 'twitter' in field_name:
                example_structure[field_name] = "https://twitter.com/example"
            elif 'description' in field_name or 'about' in field_name:
                example_structure[field_name] = "This is a company that specializes in software development."
            elif 'nom_entreprise' in field_name or 'company' in field_name:
                example_structure[field_name] = "Example Company, Inc."
            elif 'secteur' in field_name or 'industry' in field_name:
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
        
        # Field mapping instructions
        field_mapping_instructions = []
        for common_field, structure_field in exact_field_mapping.items():
            if structure_field in required_fields:
                field_mapping_instructions.append(f"- Map '{common_field}' data to the required field name '{structure_field}'")
            else:
                field_mapping_instructions.append(f"- Map '{common_field}' data to field name '{structure_field}'")
        
        field_mapping_text = "\n".join(field_mapping_instructions)
        
        structure_guidance = f"""
CUSTOM STRUCTURE SCHEMA:
Your response MUST be a VALID JSON OBJECT that follows this exact schema with these EXACT field names:
{json.dumps(structure_schema, indent=2)}

REQUIRED FIELDS (MUST be included in your response):
{required_fields_str}

EXAMPLE RESPONSE FORMAT:
{json.dumps(example_structure, indent=2)}

FIELD DESCRIPTIONS:
{json.dumps(field_descriptions, indent=2)}

FIELD MAPPING INSTRUCTIONS:
When you find content in the HTML, use these exact field names:
{field_mapping_text}

CRITICAL REQUIREMENTS:
1. ALWAYS use the EXACT field names from the schema (like '{", ".join([field.get("name") for field in structure_schema[:3]])}')
2. Never substitute or modify the field names - use them EXACTLY as specified
3. Required fields MUST be included with at least empty string values if not found
4. DO NOT invent data - if information isn't in the HTML, use empty strings or default values
5. DO NOT use field names like 'nom', 'email', etc. - use ONLY the exact schema field names
6. DO NOT add any fields that aren't in the schema
7. DO NOT add explanations or markdown, ONLY return the JSON object
"""
    
    # Standard prompt for generic extraction
    standard_guidance = """
When extracting structured data, follow these guidelines:
1. For contact information, look for names, email addresses, phone numbers and titles/roles
2. For company information, look for name, website, description, industry, and size
3. Extract social media links (LinkedIn, Twitter, Facebook, etc.)
4. Keep data structured in the appropriate fields
"""

    prompt = f"""
You are an expert in web data extraction. Extract precise data from the HTML content below.

OBJECTIVE: {objective}

{structure_guidance if structure_schema else standard_guidance}

DATA FORMAT:
{json.dumps(response_template if structure_schema else json_structure, indent=2)}

HTML CONTENT:
{truncated_html}

CRITICAL REQUIREMENTS:
- Return ONLY a valid JSON object with the EXACT field names specified
- Return the data in EXACTLY the format shown above
- Include ALL required fields even if empty
- DO NOT include any explanations, notes, or markdown formatting
- DO NOT include code blocks like ```json``` - return ONLY the raw JSON object
- ONLY use the field names defined in the schema, do not use alternative field names
"""
    
    messages = [
        {"role": "system", "content": "You are a data extraction API that returns ONLY a valid JSON object with no explanations, markdown, or formatting."},
        {"role": "user", "content": prompt}
    ]
    
    try:
        response = send_openai_request(messages)
        
        if not response:
            logger.error("Failed to get a valid response from GPT")
            return json_structure
            
        # Try to parse the JSON from the response
        try:
            # Log the entire response for debugging
            logger.debug(f"Raw AI response: {response}")
            
            # Find JSON content between ```json and ``` if present
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].strip()
            else:
                json_str = response.strip()
            
            # Clean up the response to handle common issues
            json_str = json_str.replace('\n', ' ').strip()
            
            # Fix case where response starts with non-JSON text
            if not json_str.startswith('{'):
                possible_json_start = json_str.find('{')
                if possible_json_start >= 0:
                    json_str = json_str[possible_json_start:]
            
            # Fix case where response has trailing text after JSON
            if not json_str.endswith('}'):
                possible_json_end = json_str.rfind('}')
                if possible_json_end >= 0:
                    json_str = json_str[:possible_json_end+1]
            
            result = json.loads(json_str)
            
            # Validate the structure
            if not isinstance(result, dict):
                logger.error(f"Invalid response structure (not a dict): {result}")
                return json_structure
            
            # Check if using custom schema
            if structure_schema:
                # Verify that required fields are present
                missing_fields = []
                invalid_fields = []
                
                for field in structure_schema:
                    field_name = field.get('name')
                    is_required = field.get('required', False)
                    field_type = field.get('type', 'text')
                    
                    # Check if field is missing
                    if field_name not in result:
                        if is_required:
                            missing_fields.append(field_name)
                            # Add the missing field with default value
                            if field_type == 'number':
                                result[field_name] = 0
                            else:
                                result[field_name] = ""
                    else:
                        # Validate field type
                        value = result[field_name]
                        if field_type == 'number' and not (isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit())):
                            invalid_fields.append(f"{field_name} (expected number, got {type(value).__name__})")
                            # Convert to number if possible
                            if isinstance(value, str) and value.strip():
                                try:
                                    result[field_name] = int(value) if value.isdigit() else float(value)
                                except:
                                    result[field_name] = 0
                            else:
                                result[field_name] = 0
                        
                        # Convert empty strings or None to proper defaults
                        if value is None or (isinstance(value, str) and not value.strip()):
                            if field_type == 'number':
                                result[field_name] = 0
                            else:
                                result[field_name] = ""
                
                if missing_fields:
                    logger.warning(f"AI response missing required fields: {', '.join(missing_fields)}")
                
                if invalid_fields:
                    logger.warning(f"AI response contains invalid field types: {', '.join(invalid_fields)}")
                
                # Remove any fields not in the schema
                schema_fields = [field.get('name') for field in structure_schema]
                extra_fields = [field for field in result.keys() if field not in schema_fields]
                
                for field in extra_fields:
                    logger.warning(f"Removing extra field from AI response: {field}")
                    del result[field]
                
                logger.info(f"Successfully extracted structured data with fields: {list(result.keys())}")
            else:
                # Log the results against the structure schema for debugging
                if "contacts" in result:
                    for i, contact in enumerate(result.get("contacts", [])):
                        logger.debug(f"Contact {i+1} extracted with fields: {', '.join(contact.keys())}")
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {str(e)}")
            logger.debug(f"Raw response: {response}")
            # Return the template if using custom schema
            if structure_schema:
                return response_template
            return json_structure
            
    except Exception as e:
        logger.error(f"Error during HTML analysis: {str(e)}")
        # Return the template if using custom schema
        if structure_schema:
            return response_template
        return json_structure

def analyze_serp_with_gpt(serp_results, objective, json_structure):
    """
    Analyze SERP results to identify official website and priority links.
    
    Args:
        serp_results (list): SERP API results
        objective (str): Scraping objective
        json_structure (dict): Current JSON structure
        
    Returns:
        dict: Updated priority links and official website
    """
    if not serp_results:
        logger.warning("Empty SERP results")
        return {"official_website": "", "priority_links": []}
        
    prompt = f"""
    You are a web scraping expert. Your task:
    - Identify the official website of the organization
    - Collect additional relevant pages (contact info, tenders, etc.)
    
    SERP RESULTS:
    {json.dumps(serp_results, indent=2)}
    
    EXISTING DATA:
    {json.dumps(json_structure, indent=2)}
    
    RULES:
    - The official website must be from a legitimate domain for the organization
    - Other useful links should be categorized as "priority_links"
    - Don't include social media or generic directory links (like Facebook, LinkedIn, Yellow Pages)
    
    Return your response as valid JSON in this format:
    {
        "official_website": "https://example.com",
        "priority_links": ["https://example.com/contact", "https://example.com/tenders"]
    }
    """
    
    messages = [
        {"role": "system", "content": "You are a web scraping expert selecting official sites and relevant links."},
        {"role": "user", "content": prompt}
    ]
    
    try:
        response = send_openai_request(messages)
        
        if not response:
            logger.error("Failed to get a valid response from GPT")
            return {"official_website": "", "priority_links": []}
            
        # Try to parse the JSON from the response
        try:
            # Find JSON content between ```json and ``` if present
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].strip()
            else:
                json_str = response.strip()
                
            result = json.loads(json_str)
            
            # Validate the structure
            if not isinstance(result, dict) or "priority_links" not in result:
                logger.error(f"Invalid response structure: {result}")
                return {"official_website": "", "priority_links": []}
                
            logger.info(f"Successfully extracted SERP data: {len(result.get('priority_links', []))} priority links")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {str(e)}")
            logger.debug(f"Raw response: {response}")
            return {"official_website": "", "priority_links": []}
            
    except Exception as e:
        logger.error(f"Error during SERP analysis: {str(e)}")
        return {"official_website": "", "priority_links": []}
        
def analyze_next_action_with_gpt(json_structure, html_content):
    """
    Determines the next action after analyzing HTML content.
    
    Args:
        json_structure (dict): Current JSON structure
        html_content (str): Formatted HTML content
        
    Returns:
        str: Next action recommendation
    """
    if not html_content or len(html_content.strip()) < 100:
        logger.warning("HTML content too short for next action analysis")
        return "go_next_page_from_data"
        
    # Truncate HTML content if it's too long
    truncated_html = html_content[:10000] if len(html_content) > 10000 else html_content
    
    # Get explored links from the structure
    explored_links = json_structure.get("mairie", {}).get("meta_data", {}).get("explored_links", [])
    
    prompt = f"""
    You are a scraping assistant. Given the extracted data and current page HTML:
    
    EXTRACTED DATA:
    {json.dumps(json_structure, indent=2)}
    
    CURRENT PAGE HTML:
    {truncated_html}
    
    ALREADY EXPLORED LINKS:
    {json.dumps(explored_links, indent=2)}
    
    DECIDE WHAT TO DO NEXT:
    1. If this page has useful information but we need more, find a link to follow
    2. If this page has no useful information, suggest moving to the next page from the data
    3. If we have collected enough information, suggest stopping
    
    Return your decision as JSON:
    {
        "action": "click_on_link", // or "go_next_page_from_data" or "stop_spider"
        "href": "https://example.com/next-link" // only if action is "click_on_link"
    }
    """
    
    messages = [
        {"role": "system", "content": "You are a scraping assistant that helps decide the next action."},
        {"role": "user", "content": prompt}
    ]
    
    try:
        response = send_openai_request(messages)
        
        if not response:
            logger.error("Failed to get a valid response for next action")
            return "go_next_page_from_data"
            
        # Try to parse the JSON from the response
        try:
            # Find JSON content between ```json and ``` if present
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].strip()
            else:
                json_str = response.strip()
                
            result = json.loads(json_str)
            
            # Validate the structure
            if not isinstance(result, dict) or "action" not in result:
                logger.error(f"Invalid next action response: {result}")
                return "go_next_page_from_data"
            
            action = result.get("action")
            
            if action == "click_on_link" and "href" in result:
                next_href = result["href"]
                if next_href in explored_links:
                    logger.info(f"Ignoring already explored link: {next_href}")
                    return "go_next_page_from_data"
                
                logger.info(f"Next action: Follow link {next_href}")
                return next_href
                
            elif action in ["go_next_page_from_data", "stop_spider"]:
                logger.info(f"Next action: {action}")
                return action
                
            else:
                logger.error(f"Invalid action type: {action}")
                return "go_next_page_from_data"
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse next action JSON: {str(e)}")
            return "go_next_page_from_data"
            
    except Exception as e:
        logger.error(f"Error determining next action: {str(e)}")
        return "go_next_page_from_data" 