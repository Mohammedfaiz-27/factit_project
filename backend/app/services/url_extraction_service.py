from google import genai
from app.core.config import GEMINI_API_KEY, GEMINI_MODEL
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse
import urllib3
import sys

# Disable SSL warnings when we need to bypass SSL verification
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Helper function for safe console output on Windows
def safe_print(text):
    """Print text safely, handling Unicode errors on Windows consoles"""
    try:
        print(text)
    except UnicodeEncodeError:
        # Fallback: encode as ASCII with replacement characters
        safe_text = text.encode('ascii', errors='replace').decode('ascii')
        print(safe_text)


class URLExtractionService:
    """
    Service for extracting article content and claims from URLs.
    """

    def __init__(self):
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY environment variable is not set")
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.model = GEMINI_MODEL

    def extract_from_url(self, url: str) -> dict:
        """
        Extract article content and identify main claims from a URL.

        Args:
            url (str): The URL to extract content from

        Returns:
            dict: {
                "text": extracted_article_text,
                "main_claim": identified_claim,
                "title": article_title,
                "source": domain,
                "error": error_message (if any)
            }
        """
        try:
            # Validate URL format and add scheme if missing
            parsed_url = urlparse(url)
            if not parsed_url.scheme:
                # Auto-add https:// if no scheme provided
                url = f"https://{url}"
                parsed_url = urlparse(url)

            safe_print(f"\n{'='*60}")
            safe_print(f"URL EXTRACTION: {url}")
            safe_print(f"{'='*60}\n")

            # Step 1: Fetch the webpage
            safe_print("[1/3] Fetching webpage content...")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                # Note: Don't request gzip encoding - let requests handle it automatically
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Cache-Control': 'max-age=0'
            }

            # Try with SSL verification first, then without if it fails
            try:
                response = requests.get(url, headers=headers, timeout=20, verify=True)
                response.raise_for_status()
            except requests.exceptions.SSLError:
                safe_print("[WARNING] SSL verification failed, retrying without SSL verification...")
                response = requests.get(url, headers=headers, timeout=20, verify=False)
                response.raise_for_status()

            safe_print(f"[SUCCESS] Webpage fetched successfully (Status: {response.status_code})")

            # Step 2: Parse HTML and extract text
            safe_print("[2/3] Parsing HTML content...")
            # Use response.content (raw bytes) - BeautifulSoup handles encoding
            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract title
            title = ""
            if soup.title:
                title = soup.title.string.strip() if soup.title.string else ""
            elif soup.find('h1'):
                title = soup.find('h1').get_text().strip()

            # Remove unwanted elements
            for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe', 'noscript']):
                element.decompose()

            # Try to find the main article content
            article_text = ""

            # Look for common article containers (prioritize main and specific classes)
            article_selectors = [
                'main',  # Try main first (most semantic)
                '.article-content',
                '.post-content',
                '.entry-content',
                '.story-body',
                '.article-body',
                '[role="article"]',
                'article'  # Try generic article last (might match navigation/sidebars)
            ]

            for selector in article_selectors:
                article_element = soup.select_one(selector)
                if article_element:
                    # Extract text from paragraphs
                    paragraphs = article_element.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
                    extracted_text = '\n\n'.join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])

                    # If we found substantial content, use it
                    if len(extracted_text) > 200:
                        article_text = extracted_text
                        break
                    # Keep the best result so far even if < 200 chars
                    elif len(extracted_text) > len(article_text):
                        article_text = extracted_text

            # Fallback: extract all paragraphs if no article container found
            if not article_text or len(article_text) < 200:
                paragraphs = soup.find_all('p')
                article_text = '\n\n'.join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])

            # Clean up the text
            article_text = self._clean_text(article_text)

            # Accept even minimal content - no rejection
            if not article_text:
                article_text = ""

            safe_print(f"[SUCCESS] Article text extracted ({len(article_text)} characters)")
            if title:
                safe_print(f"Title: {title[:100]}...")
            safe_print(f"Source: {parsed_url.netloc}")

            # Step 3: Use Gemini to identify main claims
            # Even if article_text is minimal, attempt to extract claim from title or URL
            safe_print("\n[3/3] Analyzing content to identify main factual claims...")
            main_claim = self._extract_main_claim(article_text, title, url)

            safe_print(f"[SUCCESS] Main claim identified ({len(main_claim)} chars)")

            return {
                "text": article_text,
                "main_claim": main_claim,
                "title": title,
                "source": parsed_url.netloc,
                "error": None
            }

        except requests.exceptions.Timeout:
            # No rejection - create a claim from the URL itself
            safe_print(f"[NOTICE] Request timeout, proceeding with URL as claim")
            parsed_url = urlparse(url)
            return {
                "text": f"This URL took too long to respond (>20 seconds): {url}",
                "main_claim": f"Information from the URL: {url}",
                "title": parsed_url.netloc or url,
                "source": parsed_url.netloc if parsed_url else url,
                "error": None
            }

        except requests.exceptions.ConnectionError as e:
            # No rejection - create a claim from the URL itself
            safe_print(f"[NOTICE] Connection error, proceeding with URL as claim")
            parsed_url = urlparse(url)
            return {
                "text": f"Could not fetch content from this URL (connection issue): {url}",
                "main_claim": f"Information regarding the URL: {url}",
                "title": parsed_url.netloc or url,
                "source": parsed_url.netloc if parsed_url else url,
                "error": None
            }

        except requests.exceptions.SSLError as e:
            # No rejection - create a claim from the URL itself
            safe_print(f"[NOTICE] SSL error, proceeding with URL as claim")
            parsed_url = urlparse(url)
            return {
                "text": f"SSL certificate issue with this URL: {url}",
                "main_claim": f"Content related to the URL: {url}",
                "title": parsed_url.netloc or url,
                "source": parsed_url.netloc if parsed_url else url,
                "error": None
            }

        except requests.exceptions.HTTPError as e:
            # No rejection - create a claim from the URL itself
            safe_print(f"[NOTICE] HTTP error {e.response.status_code if hasattr(e, 'response') else 'unknown'}, proceeding with URL as claim")
            parsed_url = urlparse(url)
            return {
                "text": f"HTTP error when accessing this URL: {url}",
                "main_claim": f"Information from the URL: {url}",
                "title": parsed_url.netloc or url,
                "source": parsed_url.netloc if parsed_url else url,
                "error": None
            }

        except Exception as e:
            # No rejection - create a claim from the URL itself
            safe_print(f"[NOTICE] Error occurred, proceeding with URL as claim: {str(e)}")
            import traceback
            safe_print(f"[DEBUG] Traceback:")
            traceback.print_exc()
            parsed_url = urlparse(url)
            return {
                "text": f"Unable to extract content from this URL: {url}",
                "main_claim": f"Information about the URL: {url}",
                "title": parsed_url.netloc or url,
                "source": parsed_url.netloc if parsed_url else url,
                "error": None
            }

    def _clean_text(self, text: str) -> str:
        """Clean extracted text by removing extra whitespace and noise."""
        # Remove multiple newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Remove multiple spaces
        text = re.sub(r' {2,}', ' ', text)
        # Remove leading/trailing whitespace from each line
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)
        return text.strip()

    def _extract_main_claim(self, article_text: str, title: str, url: str = "") -> str:
        """
        Use Gemini to identify the main factual claim(s) from the article.

        Args:
            article_text (str): The full article text
            title (str): The article title
            url (str): The source URL (fallback if no content)

        Returns:
            str: The main claim(s) to fact-check
        """
        try:
            # If no content available, use URL and title as the claim
            if not article_text or len(article_text) < 50:
                if title:
                    return f"Claims or information related to: {title} (Source: {url})"
                else:
                    return f"Information and claims from the URL: {url}"

            # Truncate article if too long (keep first 5000 chars for analysis)
            truncated_text = article_text[:5000] if len(article_text) > 5000 else article_text

            chat = self.client.chats.create(model=self.model)

            claim_extraction_prompt = f"""
You are analyzing a news article or web content to identify the main factual claim(s) that should be fact-checked.

TITLE: {title}

ARTICLE CONTENT:
{truncated_text}

Task: Extract and summarize the PRIMARY factual claim(s) made in this article. Focus on:
1. Specific statements that can be verified or disproven
2. Key facts, statistics, or assertions
3. Main thesis or conclusion if factual in nature

Guidelines:
- Combine related claims into a coherent statement
- Avoid opinions or subjective statements
- Focus on what can be fact-checked
- Be concise but complete (1-3 sentences)
- If multiple important claims exist, list them clearly

Format your response as:
MAIN CLAIM: [the primary factual claim(s) to fact-check]
"""

            response = chat.send_message(claim_extraction_prompt)
            result = response.text.strip()

            # Extract the claim from the response
            if "MAIN CLAIM:" in result:
                main_claim = result.split("MAIN CLAIM:")[1].strip()
            else:
                main_claim = result

            return main_claim

        except Exception as e:
            safe_print(f"[WARNING] Error extracting main claim with Gemini: {str(e)}")
            # Fallback: use title + first paragraph, or URL if nothing else
            if article_text and len(article_text) > 0:
                first_para = article_text.split('\n\n')[0] if '\n\n' in article_text else article_text[:500]
                return f"{title}. {first_para[:300]}" if title else first_para[:300]
            elif title:
                return f"Claims from: {title} (Source: {url})"
            else:
                return f"Information from the URL: {url}"
