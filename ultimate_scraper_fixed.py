# ultimate_scraper_fixed.py
import os
import sys
import subprocess
import importlib
import time
import re
import json
from datetime import datetime

def install_packages():
    """Automatically install required packages"""
    packages = [
        'undetected-chromedriver',
        'selenium', 
        'webdriver-manager',
        'beautifulsoup4',
        'requests'
    ]
    
    print("🔧 Installing required packages...")
    
    for package in packages:
        try:
            # Try to import first to check if already installed
            if package == 'undetected-chromedriver':
                import undetected_chromedriver
            elif package == 'beautifulsoup4':
                from bs4 import BeautifulSoup
            elif package == 'webdriver-manager':
                from webdriver_manager.chrome import ChromeDriverManager
            else:
                importlib.import_module(package.replace('-', '_'))
                
            print(f"✅ {package} already installed")
            
        except ImportError:
            print(f"📦 Installing {package}...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                print(f"✅ {package} installed successfully")
            except subprocess.CalledProcessError:
                print(f"❌ Failed to install {package}")
                return False
                
    return True

class UltimateScraper:
    """Fixed scraper that extracts entire website content"""
    
    def __init__(self):
        self.visited_urls = set()
        self.all_data = {
            'pages': [],
            'emails': set(),
            'phones': set(),
            'addresses': set(),
            'social_links': set(),
            'business_info': {
                'name': '',
                'about': '',
                'services': [],
                'hours': '',
                'products': []
            }
        }
    
    def setup_driver(self):
        """Setup undetected Chrome driver"""
        try:
            import undetected_chromedriver as uc
            
            options = uc.ChromeOptions()
            # Remove headless to see what's happening during development
            # options.add_argument("--headless")  
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-features=VizDisplayCompositor")
            options.add_argument("--disable-background-timer-throttling")
            options.add_argument("--disable-backgrounding-occluded-windows")
            options.add_argument("--disable-renderer-backgrounding")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            print("🚀 Starting undetected browser...")
            driver = uc.Chrome(options=options)
            
            # Execute stealth scripts
            driver.execute_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            """)
            
            return driver
            
        except Exception as e:
            print(f"❌ Failed to setup driver: {e}")
            return None
    
    def extract_comprehensive_info(self, html, url):
        """Extract all possible information from HTML"""
        from bs4 import BeautifulSoup
        
        page_data = {
            'url': url,
            'title': '',
            'emails': [],
            'phones': [],
            'addresses': [],
            'social_links': [],
            'text_content': '',
            'meta_description': '',
            'services': [],
            'structured_data': []
        }
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract title
            if soup.title:
                page_data['title'] = soup.title.string.strip() if soup.title.string else ''
            
            # Extract meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                page_data['meta_description'] = meta_desc['content'].strip()
            
            # Get all text content (cleaned)
            for script in soup(["script", "style"]):
                script.decompose()
            page_data['text_content'] = soup.get_text(separator=' ', strip=True)
            
            # Extract emails from entire HTML
            emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', html)
            page_data['emails'] = list(set(emails))
            self.all_data['emails'].update(emails)
            
            # Extract phones
            phone_patterns = [
                r'\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}',
                r'\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}',
                r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
            ]
            phones = []
            for pattern in phone_patterns:
                phones.extend(re.findall(pattern, html))
            page_data['phones'] = list(set(phones))
            self.all_data['phones'].update(phones)
            
            # Extract addresses
            address_patterns = [
                r'\d+\s+[\w\s]+,?\s*[\w\s]+,?\s*[A-Z]{2},?\s*\d{5}',
                r'\d+\s+[\w\s]+\s+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln),?\s*[\w\s]+,?\s*[A-Z]{2}',
            ]
            addresses = []
            for pattern in address_patterns:
                addresses.extend(re.findall(pattern, html, re.IGNORECASE))
            page_data['addresses'] = list(set(addresses))
            self.all_data['addresses'].update(addresses)
            
            # Extract social links
            social_patterns = {
                'facebook': r'https?://(?:www\.)?facebook\.com/[^\s"\'<>]+',
                'twitter': r'https?://(?:www\.)?(?:twitter\.com|x\.com)/[^\s"\'<>]+',
                'linkedin': r'https?://(?:www\.)?linkedin\.com/[^\s"\'<>]+',
                'instagram': r'https?://(?:www\.)?instagram\.com/[^\s"\'<>]+',
                'youtube': r'https?://(?:www\.)?youtube\.com/[^\s"\'<>]+'
            }
            social_links = []
            for platform, pattern in social_patterns.items():
                matches = re.findall(pattern, html, re.IGNORECASE)
                for match in matches:
                    social_links.append(f"{platform}: {match}")
            page_data['social_links'] = social_links
            self.all_data['social_links'].update(social_links)
            
            # Extract services from page content
            services_keywords = ['service', 'solution', 'consulting', 'legal', 'immigration', 'help']
            services = []
            for element in soup.find_all(['h1', 'h2', 'h3', 'h4', 'p', 'li']):
                text = element.get_text().strip().lower()
                if any(keyword in text for keyword in services_keywords):
                    services.append(element.get_text().strip())
            page_data['services'] = list(set(services))[:10]  # Limit to 10
            
            # Extract structured data (JSON-LD)
            script_tags = soup.find_all('script', type='application/ld+json')
            for script in script_tags:
                try:
                    data = json.loads(script.string)
                    page_data['structured_data'].append(data)
                except:
                    pass
            
            # Update business info
            if not self.all_data['business_info']['name'] and page_data['title']:
                self.all_data['business_info']['name'] = page_data['title']
            if not self.all_data['business_info']['about'] and page_data['meta_description']:
                self.all_data['business_info']['about'] = page_data['meta_description']
            
            self.all_data['business_info']['services'].extend(page_data['services'])
            
        except Exception as e:
            print(f"❌ Error extracting info: {e}")
        
        return page_data
    
    def find_internal_links(self, html, base_url):
        """Find all internal links to crawl"""
        from bs4 import BeautifulSoup
        import urllib.parse
        
        links = set()
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                
                # Skip external links, javascript, mailto, etc.
                if href.startswith(('http://', 'https://')):
                    if base_url in href:
                        links.add(href)
                elif href.startswith('/'):
                    parsed_base = urllib.parse.urlparse(base_url)
                    full_url = f"{parsed_base.scheme}://{parsed_base.netloc}{href}"
                    links.add(full_url)
                elif href.startswith('./') or (not href.startswith(('#', 'javascript:', 'mailto:', 'tel:'))):
                    full_url = urllib.parse.urljoin(base_url, href)
                    links.add(full_url)
                    
        except Exception as e:
            print(f"❌ Error finding links: {e}")
        
        return list(links)
    
    def crawl_website(self, start_url, max_pages=10):
        """Crawl the entire website"""
        driver = self.setup_driver()
        if not driver:
            return None
        
        try:
            urls_to_crawl = [start_url]
            crawled_count = 0
            
            while urls_to_crawl and crawled_count < max_pages:
                current_url = urls_to_crawl.pop(0)
                
                if current_url in self.visited_urls:
                    continue
                
                print(f"🔍 Crawling ({crawled_count + 1}/{max_pages}): {current_url}")
                
                try:
                    # Navigate to page
                    driver.get(current_url)
                    time.sleep(3)  # Wait for page load
                    
                    # Get page source
                    html = driver.page_source
                    
                    # Extract comprehensive information
                    page_data = self.extract_comprehensive_info(html, current_url)
                    self.all_data['pages'].append(page_data)
                    self.visited_urls.add(current_url)
                    crawled_count += 1
                    
                    print(f"   ✅ Found: {len(page_data['emails'])} emails, {len(page_data['phones'])} phones")
                    
                    # Find new links to crawl (only from main domain)
                    if crawled_count < max_pages:
                        new_links = self.find_internal_links(html, start_url)
                        for link in new_links:
                            if link not in self.visited_urls and link not in urls_to_crawl:
                                urls_to_crawl.append(link)
                    
                    # Small delay between requests
                    time.sleep(2)
                    
                except Exception as e:
                    print(f"   ❌ Failed to crawl {current_url}: {e}")
                    continue
                    
        finally:
            driver.quit()
        
        return self.all_data
    
    def save_results(self, website_url):
        """Save all results to files"""
        os.makedirs('scraping_results', exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        domain = website_url.replace('https://', '').replace('http://', '').split('/')[0]
        
        # Save comprehensive JSON
        json_filename = f"scraping_results/comprehensive_data_{domain}_{timestamp}.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            # Convert sets to lists for JSON serialization
            json_data = {
                'pages': self.all_data['pages'],
                'emails': list(self.all_data['emails']),
                'phones': list(self.all_data['phones']),
                'addresses': list(self.all_data['addresses']),
                'social_links': list(self.all_data['social_links']),
                'business_info': self.all_data['business_info']
            }
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        
        # Save summary CSV
        csv_filename = f"scraping_results/summary_{domain}_{timestamp}.csv"
        with open(csv_filename, 'w', encoding='utf-8') as f:
            f.write("BUSINESS INFORMATION SUMMARY\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Website: {website_url}\n")
            f.write(f"Scraped: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Pages Crawled: {len(self.all_data['pages'])}\n\n")
            
            f.write("CONTACT INFORMATION:\n")
            f.write(f"Emails Found: {len(self.all_data['emails'])}\n")
            for email in sorted(self.all_data['emails']):
                f.write(f"  - {email}\n")
            
            f.write(f"\nPhones Found: {len(self.all_data['phones'])}\n")
            for phone in sorted(self.all_data['phones']):
                f.write(f"  - {phone}\n")
            
            f.write(f"\nAddresses Found: {len(self.all_data['addresses'])}\n")
            for address in sorted(self.all_data['addresses']):
                f.write(f"  - {address}\n")
            
            f.write(f"\nSocial Links Found: {len(self.all_data['social_links'])}\n")
            for social in sorted(self.all_data['social_links']):
                f.write(f"  - {social}\n")
        
        return json_filename, csv_filename

def main():
    """Main function"""
    print("🎯 ULTIMATE WEBSITE SCRAPER - COMPREHENSIVE EXTRACTION")
    print("=" * 60)
    
    # Auto-install packages
    if not install_packages():
        print("❌ Some packages failed to install.")
        return
    
    print("\n✅ All packages ready!")
    
    # Get URL
    url = input("\n🌐 Enter website URL (or press Enter for purilegalservices.ca): ").strip()
    if not url:
        url = "https://purilegalservices.ca"
    
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    print(f"\n🎯 Target: {url}")
    print("🚀 Starting comprehensive website extraction...")
    print("⏳ This may take a few minutes...\n")
    
    # Initialize scraper
    scraper = UltimateScraper()
    
    # Crawl website (up to 10 pages)
    results = scraper.crawl_website(url, max_pages=10)
    
    # Save results
    if results:
        json_file, csv_file = scraper.save_results(url)
        
        print("\n" + "=" * 60)
        print("📊 EXTRACTION COMPLETE!")
        print("=" * 60)
        
        print(f"✅ Pages crawled: {len(results['pages'])}")
        print(f"📧 Emails found: {len(results['emails'])}")
        print(f"📞 Phones found: {len(results['phones'])}")
        print(f"📍 Addresses found: {len(results['addresses'])}")
        print(f"🔗 Social links found: {len(results['social_links'])}")
        
        print(f"\n💾 Files saved:")
        print(f"   📄 Comprehensive data: {json_file}")
        print(f"   📊 Summary report: {csv_file}")
        
        # Show some findings
        if results['emails']:
            print(f"\n📧 Emails: {', '.join(sorted(results['emails']))}")
        if results['phones']:
            print(f"📞 Phones: {', '.join(sorted(results['phones']))}")
            
    else:
        print("❌ Extraction failed! The website might have strong protection.")
    
    print(f"\n🎯 Done! Press Enter to exit...")
    input()

if __name__ == "__main__":
    main()