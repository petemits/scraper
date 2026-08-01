# business_scraper.py
import urllib.request
import urllib.parse
import urllib.error
import csv
import os
import re
import time
import http.server
import socketserver
import json
import threading
from datetime import datetime
from html import escape
from bs4 import BeautifulSoup
import ssl

# Disable SSL verification for easier scraping
ssl._create_default_https_context = ssl._create_unverified_context

class BusinessScraper:
    def __init__(self):
        self.visited_urls = set()
        self.contact_info = {
            'emails': set(),
            'phones': set(),
            'addresses': set(),
            'social_links': set()
        }
        self.business_info = {
            'about': '',
            'services': [],
            'products': [],
            'hours': '',
            'name': '',
            'website': ''
        }
    
    def make_request(self, url):
        """Make HTTP request using urllib with better error handling"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            req = urllib.request.Request(url, headers=headers)
            response = urllib.request.urlopen(req, timeout=20)
            
            # Check content type
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' not in content_type:
                print(f"Skipping non-HTML content: {content_type}")
                return None
                
            html_content = response.read().decode('utf-8', errors='ignore')
            return html_content
            
        except urllib.error.HTTPError as e:
            print(f"HTTP Error {e.code} for {url}: {e.reason}")
            return None
        except urllib.error.URLError as e:
            print(f"URL Error for {url}: {e.reason}")
            return None
        except Exception as e:
            print(f"Could not access {url}: {e}")
            return None

    def extract_emails(self, text):
        """Extract email addresses from text"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        return re.findall(email_pattern, text)

    def extract_phones(self, text):
        """Extract phone numbers from text"""
        # More comprehensive phone patterns
        phone_patterns = [
            r'(\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4})',
            r'(\+?[0-9]{1,3}[-.\s]?\(?[0-9]{1,4}\)?[-.\s]?[0-9]{1,4}[-.\s]?[0-9]{1,9})',
            r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
            r'\b\(\d{3}\)\s*\d{3}[-.]?\d{4}\b',
        ]
        
        phones = []
        for pattern in phone_patterns:
            found = re.findall(pattern, text)
            phones.extend(found)
        
        # Clean phone numbers
        cleaned_phones = []
        for phone in phones:
            # Remove common separators and keep only digits and +
            clean_phone = re.sub(r'[^\d+]', '', phone)
            if len(clean_phone) >= 10:  # Valid phone numbers should have at least 10 digits
                cleaned_phones.append(clean_phone)
        
        return cleaned_phones

    def extract_contact_info(self, html):
        """Extract all contact information from page using multiple methods"""
        if not html:
            return
            
        # Use BeautifulSoup for more reliable parsing
        try:
            soup = BeautifulSoup(html, 'html.parser')
            text_content = soup.get_text()
        except:
            text_content = html

        # Extract emails from text
        emails = self.extract_emails(text_content)
        self.contact_info['emails'].update(emails)
        
        # Extract emails from mailto links
        mailto_pattern = r'mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        mailto_matches = re.findall(mailto_pattern, html, re.IGNORECASE)
        self.contact_info['emails'].update(mailto_matches)
        
        # Extract phones from text
        phones = self.extract_phones(text_content)
        self.contact_info['phones'].update(phones)
        
        # Extract phones from tel links
        tel_pattern = r'tel:([+\d\s\-\(\)\.]+)'
        tel_matches = re.findall(tel_pattern, html, re.IGNORECASE)
        for phone in tel_matches:
            clean_phone = re.sub(r'[^\d+]', '', phone)
            if len(clean_phone) >= 10:
                self.contact_info['phones'].add(clean_phone)

        # Enhanced address extraction
        address_patterns = [
            r'\d+\s+[A-Za-z0-9\s,]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Court|Ct|Place|Pl|Square|Sq|Trail|Trl|Way|Wy),?\s+[A-Za-z\s]+,\s*[A-Z]{2}\s*\d{5}',
            r'\d+\s+[A-Za-z0-9\s,]+,\s*[A-Za-z\s]+,\s*[A-Z]{2}\s*\d{5}',
            r'[A-Za-z\s]+,?\s*[A-Z]{2}\s*\d{5}',
        ]
        
        for pattern in address_patterns:
            addresses = re.findall(pattern, text_content, re.IGNORECASE)
            for address in addresses:
                if len(address) > 10:  # Basic validation
                    self.contact_info['addresses'].add(address.strip())

        # Enhanced social media extraction
        social_patterns = {
            'facebook': r'https?://(?:www\.)?facebook\.com/[A-Za-z0-9.\-]+',
            'twitter': r'https?://(?:www\.)?(?:twitter\.com|x\.com)/[A-Za-z0-9_]+',
            'linkedin': r'https?://(?:www\.)?linkedin\.com/(?:company/|in/)?[A-Za-z0-9\-]+',
            'instagram': r'https?://(?:www\.)?instagram\.com/[A-Za-z0-9._]+',
            'youtube': r'https?://(?:www\.)?youtube\.com/(?:channel/|user/)?[A-Za-z0-9\-]+'
        }
        
        for platform, pattern in social_patterns.items():
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                self.contact_info['social_links'].add(f"{platform}: {match}")

    def extract_business_info(self, html):
        """Extract business information from page using BeautifulSoup"""
        if not html:
            return
            
        try:
            soup = BeautifulSoup(html, 'html.parser')
        except:
            return

        # Extract business name
        if not self.business_info['name']:
            # Try title first
            title_tag = soup.find('title')
            if title_tag:
                title_text = title_tag.get_text().strip()
                self.business_info['name'] = re.split(r'[|\-–]', title_text)[0].strip()
            
            # Try h1 if no title
            if not self.business_info['name']:
                h1_tag = soup.find('h1')
                if h1_tag:
                    self.business_info['name'] = h1_tag.get_text().strip()

        # Extract meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            self.business_info['about'] = meta_desc['content'].strip()
        
        # If no meta description, look for the first paragraph
        if not self.business_info['about']:
            first_para = soup.find('p')
            if first_para:
                para_text = first_para.get_text().strip()
                if len(para_text) > 50 and len(para_text) < 500:
                    self.business_info['about'] = para_text

        # Enhanced services extraction
        service_keywords = ['service', 'solution', 'offer', 'provide', 'expert', 'special']
        
        # Look for services in headings and lists
        for tag in soup.find_all(['h2', 'h3', 'h4', 'li', 'div']):
            text = tag.get_text().strip().lower()
            if any(keyword in text for keyword in service_keywords):
                parent_text = tag.get_text().strip()
                if len(parent_text) > 10 and len(parent_text) < 200:
                    self.business_info['services'].append(parent_text)
        
        # Remove duplicates and clean up
        self.business_info['services'] = list(set(self.business_info['services']))[:20]

        # Extract business hours with multiple patterns
        hours_patterns = [
            r'Monday.*?Sunday.*?\d{1,2}:\d{2}.*?\d{1,2}:\d{2}',
            r'\d{1,2}:\d{2}\s*[apm]*\s*-\s*\d{1,2}:\d{2}\s*[apm]*',
            r'Mon.*?Fri.*?\d{1,2}:\d{2}',
            r'Hours?:\s*([^<]+)',
            r'Business Hours?:\s*([^<]+)'
        ]
        
        text_content = soup.get_text()
        for pattern in hours_patterns:
            hours_match = re.search(pattern, text_content, re.IGNORECASE | re.DOTALL)
            if hours_match:
                hours_text = hours_match.group(0).strip()
                if len(hours_text) > 5 and len(hours_text) < 200:
                    self.business_info['hours'] = hours_text
                    break

    def extract_structured_data(self, html):
        """Extract structured data (JSON-LD, Microdata) from the page"""
        if not html:
            return
            
        # JSON-LD extraction
        json_ld_pattern = r'<script[^>]*type=[\'"]application/ld\+json[\'"][^>]*>(.*?)</script>'
        json_ld_matches = re.findall(json_ld_pattern, html, re.IGNORECASE | re.DOTALL)
        
        for json_ld in json_ld_matches:
            try:
                data = json.loads(json_ld)
                if isinstance(data, dict):
                    # Handle different types of businesses
                    if data.get('@type') in ['LocalBusiness', 'Attorney', 'Organization', 'ProfessionalService']:
                        if 'name' in data and not self.business_info['name']:
                            self.business_info['name'] = data['name']
                        if 'description' in data and not self.business_info['about']:
                            self.business_info['about'] = data['description']
                        if 'telephone' in data:
                            self.contact_info['phones'].add(data['telephone'])
                        if 'email' in data:
                            self.contact_info['emails'].add(data['email'])
                        if 'address' in data:
                            if isinstance(data['address'], dict):
                                address_parts = []
                                for key in ['streetAddress', 'addressLocality', 'addressRegion', 'postalCode']:
                                    if key in data['address']:
                                        address_parts.append(str(data['address'][key]))
                                if address_parts:
                                    self.contact_info['addresses'].add(', '.join(address_parts))
                            elif isinstance(data['address'], str):
                                self.contact_info['addresses'].add(data['address'])
            except:
                continue

    def crawl_page(self, url, depth=0, max_depth=3):
        """Crawl a single page and related pages with enhanced discovery"""
        if depth > max_depth or url in self.visited_urls:
            return
        
        self.visited_urls.add(url)
        print(f"🔍 Scanning ({depth}): {url}")
        
        html = self.make_request(url)
        if not html:
            return
        
        # Extract information from current page
        self.extract_contact_info(html)
        self.extract_business_info(html)
        self.extract_structured_data(html)
        
        # If this is the first page, look for additional pages to crawl
        if depth < max_depth:
            additional_links = self.find_additional_links(html, url)
            for link in additional_links[:5]:  # Limit to 5 additional pages
                time.sleep(1)  # Be respectful
                self.crawl_page(link, depth + 1, max_depth)

    def find_additional_links(self, html, base_url):
        """Find additional relevant pages to crawl with better discovery"""
        priority_pages = ['about', 'contact', 'services', 'team', 'location', 'hours', 'faq', 'products']
        additional_links = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            links = soup.find_all('a', href=True)
            
            for link in links:
                href = link['href']
                link_text = link.get_text().lower()
                
                try:
                    # Convert relative URLs to absolute
                    if href.startswith(('http://', 'https://')):
                        full_url = href
                    elif href.startswith('/'):
                        parsed_base = urllib.parse.urlparse(base_url)
                        full_url = f"{parsed_base.scheme}://{parsed_base.netloc}{href}"
                    elif href.startswith('./') or href.startswith('../'):
                        full_url = urllib.parse.urljoin(base_url, href)
                    elif not href.startswith(('javascript:', 'mailto:', 'tel:', '#', 'data:')):
                        full_url = urllib.parse.urljoin(base_url, href)
                    else:
                        continue
                    
                    # Normalize URL
                    full_url = full_url.split('#')[0]  # Remove fragments
                    
                    # Check if this is a relevant page
                    url_lower = full_url.lower()
                    is_relevant = (
                        any(page in url_lower for page in priority_pages) or
                        any(page in link_text for page in priority_pages) or
                        any(link_text.strip() == page for page in priority_pages)
                    )
                    
                    if is_relevant and full_url not in self.visited_urls:
                        additional_links.append(full_url)
                        
                except Exception as e:
                    continue
                    
        except Exception as e:
            print(f"Error finding additional links: {e}")
        
        return list(set(additional_links))[:10]  # Return unique links, max 10

    def analyze_business_scope(self):
        """Analyze the business scope based on collected information"""
        all_text = (self.business_info['about'] + ' ' + 
                   ' '.join(self.business_info['services']) + ' ' +
                   self.business_info['name']).lower()
        
        industry_keywords = {
            'Legal Services': ['legal', 'attorney', 'lawyer', 'law firm', 'legal services', 'court', 'dispute', 'immigration', 'advocate', 'legal advice'],
            'Consulting': ['consulting', 'advisor', 'consultant', 'strategy', 'business consulting'],
            'Real Estate': ['real estate', 'property', 'landlord', 'tenant', 'housing', 'realty'],
            'Professional Services': ['service', 'professional', 'business', 'solution', 'expert'],
            'Financial': ['financial', 'money', 'investment', 'insurance', 'banking', 'wealth'],
            'Healthcare': ['medical', 'health', 'clinic', 'hospital', 'doctor', 'healthcare'],
            'Technology': ['technology', 'software', 'tech', 'digital', 'it', 'computer'],
            'Education': ['education', 'training', 'course', 'learn', 'school']
        }
        
        detected_industries = []
        for industry, keywords in industry_keywords.items():
            if any(keyword in all_text for keyword in keywords):
                detected_industries.append(industry)
        
        return detected_industries if detected_industries else ['General Business']

    def save_to_csv(self, website_url):
        """Save all results to CSV file"""
        os.makedirs('scraping_results', exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        domain = urllib.parse.urlparse(website_url).netloc.replace('www.', '')
        filename = f"scraping_results/business_info_{domain}_{timestamp}.csv"
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header and main info
            writer.writerow(['BUSINESS INFORMATION REPORT'])
            writer.writerow([])
            writer.writerow(['Website URL:', website_url])
            writer.writerow(['Scraping Date:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
            writer.writerow(['Business Name:', self.business_info.get('name', 'Not found')])
            writer.writerow(['Business Scope:', ', '.join(self.analyze_business_scope())])
            writer.writerow(['Pages Scanned:', len(self.visited_urls)])
            writer.writerow([])
            
            # Contact Information
            writer.writerow(['CONTACT INFORMATION'])
            writer.writerow([])
            
            writer.writerow(['EMAIL ADDRESSES', f'Found: {len(self.contact_info["emails"])}'])
            for email in sorted(self.contact_info['emails']):
                writer.writerow(['', email])
            writer.writerow([])
            
            writer.writerow(['PHONE NUMBERS', f'Found: {len(self.contact_info["phones"])}'])
            for phone in sorted(self.contact_info['phones']):
                writer.writerow(['', phone])
            writer.writerow([])
            
            writer.writerow(['ADDRESSES', f'Found: {len(self.contact_info["addresses"])}'])
            for address in sorted(self.contact_info['addresses']):
                writer.writerow(['', address])
            writer.writerow([])
            
            writer.writerow(['SOCIAL MEDIA LINKS', f'Found: {len(self.contact_info["social_links"])}'])
            for social in sorted(self.contact_info['social_links']):
                writer.writerow(['', social])
            writer.writerow([])
            
            # Business Information
            writer.writerow(['BUSINESS PROFILE'])
            writer.writerow([])
            
            if self.business_info['about']:
                writer.writerow(['ABOUT/DESCRIPTION'])
                writer.writerow(['', self.business_info['about']])
                writer.writerow([])
            
            if self.business_info['hours']:
                writer.writerow(['BUSINESS HOURS'])
                writer.writerow(['', self.business_info['hours']])
                writer.writerow([])
            
            writer.writerow(['SERVICES/PRODUCTS', f'Found: {len(self.business_info["services"])}'])
            for service in self.business_info['services'][:15]:
                writer.writerow(['', service])
            writer.writerow([])
            
            # Pages scanned
            writer.writerow(['PAGES SCANNED'])
            for page in sorted(self.visited_urls):
                writer.writerow(['', page])
        
        return filename

    def scrape_website(self, website_url):
        """Main method to scrape a website"""
        # Reset data for new scrape
        self.visited_urls.clear()
        self.contact_info = {k: set() for k in self.contact_info}
        self.business_info = {
            'about': '',
            'services': [],
            'products': [],
            'hours': '',
            'name': '',
            'website': website_url
        }
        
        print(f"🎯 Starting to scrape: {website_url}")
        print("⏳ This may take a few moments...")
        
        # Validate URL
        if not website_url.startswith(('http://', 'https://')):
            website_url = 'https://' + website_url
        
        # Start scraping with increased depth
        start_time = time.time()
        self.crawl_page(website_url, max_depth=3)
        scraping_time = time.time() - start_time
        
        # Save to CSV
        csv_filename = self.save_to_csv(website_url)
        
        # Prepare results for display
        results = {
            'success': True,
            'website_url': website_url,
            'scraping_time': f"{scraping_time:.1f} seconds",
            'csv_filename': csv_filename,
            'pages_scanned': len(self.visited_urls),
            'business_name': self.business_info.get('name', 'Not found'),
            'business_scope': ', '.join(self.analyze_business_scope()),
            'emails_found': len(self.contact_info['emails']),
            'phones_found': len(self.contact_info['phones']),
            'addresses_found': len(self.contact_info['addresses']),
            'social_links_found': len(self.contact_info['social_links']),
            'services_found': len(self.business_info['services']),
            'emails': sorted(self.contact_info['emails']),
            'phones': sorted(self.contact_info['phones']),
            'addresses': sorted(self.contact_info['addresses']),
            'social_links': sorted(self.contact_info['social_links']),
            'services': self.business_info['services'][:15],
            'about': self.business_info['about'] or "No description found",
            'hours': self.business_info['hours'] or "No hours found"
        }
        
        return results

# ... (keep the WebScraperHandler and main function the same as before)
class WebScraperHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            html_content = self.get_html_interface()
            self.wfile.write(html_content.encode())
        else:
            super().do_GET()
    
    def do_POST(self):
        if self.path == '/scrape':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
                website_url = data.get('website_url', '').strip()
                
                if not website_url:
                    response = {'success': False, 'error': 'No website URL provided'}
                else:
                    scraper = BusinessScraper()
                    response = scraper.scrape_website(website_url)
                    
            except Exception as e:
                response = {'success': False, 'error': str(e)}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def get_html_interface(self):
        """Return the HTML interface"""
        return """
<!DOCTYPE html>
<html>
<head>
    <title>Business Web Scraper</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            text-align: center;
            margin-bottom: 30px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: bold;
            color: #555;
        }
        input[type="url"] {
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 5px;
            font-size: 16px;
            box-sizing: border-box;
        }
        button {
            background: #007bff;
            color: white;
            padding: 12px 30px;
            border: none;
            border-radius: 5px;
            font-size: 16px;
            cursor: pointer;
            width: 100%;
        }
        button:hover {
            background: #0056b3;
        }
        button:disabled {
            background: #6c757d;
            cursor: not-allowed;
        }
        .results {
            margin-top: 30px;
            display: none;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .stat-item {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            text-align: center;
        }
        .stat-number {
            font-size: 24px;
            font-weight: bold;
            color: #007bff;
        }
        .info-section {
            margin-bottom: 20px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 5px;
        }
        .info-list {
            list-style: none;
            padding: 0;
        }
        .info-list li {
            padding: 8px 0;
            border-bottom: 1px solid #ddd;
        }
        .loading {
            text-align: center;
            padding: 20px;
            display: none;
        }
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #007bff;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 10px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .success-message {
            background: #d4edda;
            color: #155724;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
        .error-message {
            background: #f8d7da;
            color: #721c24;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Business Web Scraper</h1>
        
        <div class="form-group">
            <label for="websiteUrl">Enter Website URL:</label>
            <input type="url" id="websiteUrl" placeholder="https://example.com or example.com" required>
        </div>
        
        <button onclick="startScraping()" id="scrapeBtn">Start Scraping</button>
        
        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p>Scanning website for contact information and business details...</p>
            <p><small>This may take 30-60 seconds as we scan multiple pages</small></p>
        </div>
        
        <div class="results" id="results">
            <!-- Results will be filled by JavaScript -->
        </div>
    </div>

    <script>
        function startScraping() {
            const url = document.getElementById('websiteUrl').value.trim();
            if (!url) {
                showError('Please enter a website URL');
                return;
            }
            
            document.getElementById('scrapeBtn').disabled = true;
            document.getElementById('scrapeBtn').textContent = 'Scraping... Please Wait';
            document.getElementById('loading').style.display = 'block';
            document.getElementById('results').style.display = 'none';
            
            fetch('/scrape', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ website_url: url })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                document.getElementById('loading').style.display = 'none';
                document.getElementById('scrapeBtn').disabled = false;
                document.getElementById('scrapeBtn').textContent = 'Start Scraping';
                
                if (data.success) {
                    displayResults(data);
                } else {
                    showError(data.error || 'Scraping failed');
                }
            })
            .catch(error => {
                document.getElementById('loading').style.display = 'none';
                document.getElementById('scrapeBtn').disabled = false;
                document.getElementById('scrapeBtn').textContent = 'Start Scraping';
                showError('Error: ' + error.message);
            });
        }
        
        function displayResults(data) {
            let resultsHTML = `
                <div class="success-message">
                    <strong>✅ Scraping Completed Successfully!</strong><br>
                    Results saved to: <strong>${data.csv_filename}</strong>
                </div>
                
                <div class="stats">
                    <div class="stat-item">
                        <div class="stat-number">${data.pages_scanned}</div>
                        <div>Pages Scanned</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number">${data.emails_found}</div>
                        <div>Emails Found</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number">${data.phones_found}</div>
                        <div>Phones Found</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number">${data.services_found}</div>
                        <div>Services Found</div>
                    </div>
                </div>
                
                <div class="info-section">
                    <h3>Business Information</h3>
                    <p><strong>Website:</strong> ${data.website_url}</p>
                    <p><strong>Business Name:</strong> ${data.business_name}</p>
                    <p><strong>Business Scope:</strong> ${data.business_scope}</p>
                    <p><strong>Time Taken:</strong> ${data.scraping_time}</p>
                    <p><strong>About:</strong> ${data.about}</p>
                    ${data.hours ? `<p><strong>Business Hours:</strong> ${data.hours}</p>` : ''}
                </div>
            `;
            
            // Add contact information if found
            if (data.emails.length > 0 || data.phones.length > 0 || data.addresses.length > 0 || data.social_links.length > 0) {
                resultsHTML += `<div class="info-section">
                    <h3>Contact Information</h3>`;
                
                if (data.emails.length > 0) {
                    resultsHTML += `<h4>Email Addresses (${data.emails.length} found):</h4>
                    <ul class="info-list">`;
                    data.emails.forEach(email => {
                        resultsHTML += `<li>${email}</li>`;
                    });
                    resultsHTML += `</ul>`;
                }
                
                if (data.phones.length > 0) {
                    resultsHTML += `<h4>Phone Numbers (${data.phones.length} found):</h4>
                    <ul class="info-list">`;
                    data.phones.forEach(phone => {
                        resultsHTML += `<li>${phone}</li>`;
                    });
                    resultsHTML += `</ul>`;
                }
                
                if (data.addresses.length > 0) {
                    resultsHTML += `<h4>Addresses (${data.addresses.length} found):</h4>
                    <ul class="info-list">`;
                    data.addresses.forEach(address => {
                        resultsHTML += `<li>${address}</li>`;
                    });
                    resultsHTML += `</ul>`;
                }
                
                if (data.social_links.length > 0) {
                    resultsHTML += `<h4>Social Media Links (${data.social_links.length} found):</h4>
                    <ul class="info-list">`;
                    data.social_links.forEach(social => {
                        resultsHTML += `<li>${social}</li>`;
                    });
                    resultsHTML += `</ul>`;
                }
                
                resultsHTML += `</div>`;
            }
            
            // Add services if found
            if (data.services.length > 0) {
                resultsHTML += `<div class="info-section">
                    <h3>Services & Products</h3>
                    <ul class="info-list">`;
                data.services.forEach(service => {
                    resultsHTML += `<li>${service}</li>`;
                });
                resultsHTML += `</ul></div>`;
            }
            
            resultsHTML += `
                <div style="text-align: center; margin-top: 20px;">
                    <button onclick="scrapeAnother()" style="background: #28a745; width: auto;">
                        Scrape Another Website
                    </button>
                </div>
            `;
            
            document.getElementById('results').innerHTML = resultsHTML;
            document.getElementById('results').style.display = 'block';
        }
        
        function showError(message) {
            document.getElementById('results').innerHTML = `
                <div class="error-message">
                    <strong>Error:</strong> ${message}
                </div>
                <div style="text-align: center; margin-top: 20px;">
                    <button onclick="scrapeAnother()" style="background: #dc3545; width: auto;">
                        Try Again
                    </button>
                </div>
            `;
            document.getElementById('results').style.display = 'block';
        }
        
        function scrapeAnother() {
            document.getElementById('websiteUrl').value = '';
            document.getElementById('scrapeBtn').disabled = false;
            document.getElementById('scrapeBtn').textContent = 'Start Scraping';
            document.getElementById('results').style.display = 'none';
            document.getElementById('websiteUrl').focus();
        }
        
        document.getElementById('websiteUrl').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                startScraping();
            }
        });
    </script>
</body>
</html>
"""

def main():
    """Start the web scraper server"""
    os.makedirs('scraping_results', exist_ok=True)
    
    PORT = 8000
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    handler = WebScraperHandler
    
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        print("🚀 Business Web Scraper Server Started!")
        print("📍 Access at: http://localhost:8000")
        print("💾 Results will be saved to: scraping_results/ folder")
        print("⏹️  Press Ctrl+C to stop the server")
        print("\n" + "="*50)
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 Server stopped by user")
        finally:
            httpd.server_close()

if __name__ == '__main__':
    main()