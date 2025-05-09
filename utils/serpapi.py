import requests
import logging
import time
from django.conf import settings

logger = logging.getLogger(__name__)

# API Configuration
SERPER_API_KEY = settings.SERPER_API_KEY
SERPER_API_URL = "https://google.serper.dev/search"

# Rate limiting
LAST_REQUEST_TIME = 0
MIN_DELAY_BETWEEN_REQUESTS = 1.0  # seconds

def get_serp_results(query, num_results_per_page=10, num_pages=1, page=1):
    """
    Get search engine results using Serper.dev API.
    
    Args:
        query (str): Search query
        num_results_per_page (int): Number of results per page
        num_pages (int): Number of pages to fetch
        page (int): Starting page number
        
    Returns:
        list: SERP results with URL, title, and snippet
    """
    if not SERPER_API_KEY:
        logger.error("Serper API key is missing")
        return []
    
    # Rate limiting
    global LAST_REQUEST_TIME
    current_time = time.time()
    elapsed = current_time - LAST_REQUEST_TIME
    
    if elapsed < MIN_DELAY_BETWEEN_REQUESTS:
        sleep_time = MIN_DELAY_BETWEEN_REQUESTS - elapsed
        logger.info(f"Rate limiting: Sleeping for {sleep_time:.2f} seconds")
        time.sleep(sleep_time)
    
    results = []
    
    try:
        # For single page requests, simplify to just fetch the requested page
        if isinstance(page, int) and page > 0 and num_pages == 1:
            logger.info(f"Fetching SERP page {page} for query: '{query}'")
            
            headers = {
                "X-API-KEY": SERPER_API_KEY,
                "Content-Type": "application/json"
            }
            
            payload = {
                "q": query,
                "num": num_results_per_page,
                "page": page
            }
            
            # Update last request time right before making the request
            LAST_REQUEST_TIME = time.time()
            
            response = requests.post(SERPER_API_URL, headers=headers, json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract organic results
            if "organic" in data:
                for item in data["organic"]:
                    result = {
                        "title": item.get("title", ""),
                        "url": item.get("link", ""),
                        "snippet": item.get("snippet", "")
                    }
                    results.append(result)
            
            logger.info(f"Retrieved {len(results)} results for query: '{query}' (page {page})")
            return results
        
        # For multi-page requests, fetch each page sequentially
        else:
            for p in range(page, page + num_pages):
                logger.info(f"Fetching SERP page {p} for query: '{query}'")
                
                headers = {
                    "X-API-KEY": SERPER_API_KEY,
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "q": query,
                    "num": num_results_per_page,
                    "page": p
                }
                
                # Update last request time right before making the request
                LAST_REQUEST_TIME = time.time()
                
                response = requests.post(SERPER_API_URL, headers=headers, json=payload)
                response.raise_for_status()
                
                data = response.json()
                
                # Extract organic results
                if "organic" in data:
                    page_results = []
                    for item in data["organic"]:
                        result = {
                            "title": item.get("title", ""),
                            "url": item.get("link", ""),
                            "snippet": item.get("snippet", "")
                        }
                        page_results.append(result)
                    
                    # Add this page's results to overall results
                    results.extend(page_results)
                    logger.info(f"Retrieved {len(page_results)} results from page {p}")
                    
                    # If no results on this page, stop fetching more pages
                    if not page_results:
                        logger.info(f"No results found on page {p}, stopping pagination")
                        break
                else:
                    logger.warning(f"No organic results found on page {p}")
                    break
                
                # Add a delay between pages if we have more pages to fetch
                if p < page + num_pages - 1:
                    time.sleep(MIN_DELAY_BETWEEN_REQUESTS)
            
            logger.info(f"Retrieved {len(results)} total results for query: '{query}' across pages {page}-{page+num_pages-1}")
            return results
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching SERP results: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in get_serp_results: {str(e)}")
        return [] 