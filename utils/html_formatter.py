from lxml import etree
from urllib.parse import urljoin
import logging

logger = logging.getLogger(__name__)

def extract_seo_content(html):
    """
    Extracts only relevant SEO content (H1-H3, paragraphs) from HTML.

    Args:
        html (str): The raw HTML content.

    Returns:
        str: Formatted HTML with essential SEO structure.
    """
    if not html or not html.strip():
        return ""

    try:
        parser = etree.HTMLParser(recover=True)
        root = etree.HTML(html, parser)

        if root is None:
            logger.error("Failed to parse HTML. The content may be empty or malformed.")
            return ""

        formatted_content = []

        for element in root.iter():
            if element.tag in ["h1", "h2", "h3", "p"]:
                text = element.text.strip() if element.text and element.text.strip() else ""
                if text:
                    formatted_content.append(f"<{element.tag}>{text}</{element.tag}>")

        return "\n".join(formatted_content)

    except Exception as e:
        logger.error(f"Unexpected error while parsing HTML: {e}")
        return ""

def format_extracted_html(html, url):
    """
    Extracts plain text and links from raw HTML, ignoring JavaScript and CSS.

    Args:
        html (str or bytes): Raw HTML content.
        url (str): Base URL for resolving relative links.

    Returns:
        str: Plain text with clear notation for links.
    """
    if not html or not html.strip():
        return ""

    try:
        # Ensure the input is bytes to avoid encoding issues
        if isinstance(html, str):
            html = html.encode("utf-8", "ignore")

        parser = etree.HTMLParser(recover=True)
        root = etree.HTML(html, parser)

        if root is None:
            logger.error("Failed to parse HTML. The content may be empty or malformed.")
            return ""

        formatted_content = []
        
        # Extract title
        title_element = root.xpath("//title")
        if title_element and title_element[0].text:
            formatted_content.append(f"PAGE TITLE: {title_element[0].text.strip()}")
            formatted_content.append("--------------------")
        
        # Extract meta description
        meta_desc = root.xpath("//meta[@name='description']/@content")
        if meta_desc:
            formatted_content.append(f"META DESCRIPTION: {meta_desc[0]}")
            formatted_content.append("--------------------")

        # Extract main content
        for element in root.iter():
            # Ignore script and style elements
            if element.tag in ["script", "style", "iframe", "noscript"]:
                continue

            text = element.text.strip() if element.text and element.text.strip() else ""

            if element.tag == "a" and "href" in element.attrib:
                href = element.attrib["href"]
                if href.startswith("#") or href.startswith("javascript:"):
                    continue
                    
                full_url = urljoin(url, href)
                anchor_text = text or "Lien"
                formatted_content.append(f"LINK: {anchor_text} -> {full_url}")
            
            elif element.tag in ["h1", "h2", "h3", "h4"]:
                if text:
                    formatted_content.append(f"HEADING: {text}")
            
            elif element.tag == "p":
                if text:
                    formatted_content.append(f"PARAGRAPH: {text}")
                    
            elif element.tag in ["li", "dt", "dd"]:
                if text:
                    formatted_content.append(f"LIST ITEM: {text}")
            
            elif element.tag in ["th", "td"]:
                if text:
                    formatted_content.append(f"TABLE CELL: {text}")

        # Extract contact information using XPath
        # Look for emails
        email_elements = root.xpath("//*[contains(text(), '@')]")
        if email_elements:
            formatted_content.append("--------------------")
            formatted_content.append("POTENTIAL EMAILS:")
            for elem in email_elements:
                if elem.text and '@' in elem.text:
                    formatted_content.append(elem.text.strip())
        
        # Look for phone numbers
        phone_elements = root.xpath("//*[contains(text(), 'tel') or contains(text(), 'phone') or contains(text(), 'téléphone')]")
        if phone_elements:
            formatted_content.append("--------------------")
            formatted_content.append("POTENTIAL PHONE NUMBERS:")
            for elem in phone_elements:
                if elem.text:
                    formatted_content.append(elem.text.strip())

        return "\n".join(formatted_content)

    except ValueError as ve:
        logger.error(f"ValueError while parsing HTML: {ve}")
    except UnicodeDecodeError as ude:
        logger.error(f"UnicodeDecodeError: {ude} - Trying to force decode HTML as UTF-8")
        return format_extracted_html(html.decode("utf-8", "ignore"), url)
    except Exception as e:
        logger.error(f"Unexpected error while parsing HTML: {e}")

    return "" 