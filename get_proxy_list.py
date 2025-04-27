import requests
import colorama
from colorama import Fore, Style
import re
import random
import time
from bs4 import BeautifulSoup


colorama.init(autoreset=True)
# URL of the proxy list
PROXY_URLS = [
    "https://free-proxy-list.net/",
    "https://www.sslproxies.org/",
    "https://www.us-proxy.org/",
    "https://hidemy.name/en/proxy-list/",
    "https://www.proxynova.com/proxy-server-list/",
    "https://www.proxyscrape.com/free-proxy-list",
    "https://www.proxy-list.download/",
    "https://spys.one/free-proxy-list/",
    "https://www.freeproxyclists.net/",
    "https://geonode.com/free-proxy-list/",
    "https://www.proxydocker.com/",
    "https://openproxy.space/list",
    "https://www.proxy-list.org/",
    "https://proxylist.geonode.com/",
    "https://www.socks-proxy.net/",
    "https://www.xroxy.com/proxylist.htm",
    "https://www.httptunnel.ge/ProxyListForFree.aspx",
    "https://vpnoverview.com/privacy/anonymous-browsing/free-proxy-servers/",
    "https://hidester.com/proxylist/",
    "https://www.freeproxy.world/"
]
             

# Path to save proxies
PROXY_FILE = "database/proxies.txt"


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
]

def fetch_proxies_with_regex(limit=None):
    """
    Fetch the latest proxy list from multiple proxy sites using regular expressions and save to a file.
    """
    print("[INFO] Fetching latest proxies using regex...")
    
    proxies_found = []
    successful_sites = 0

    try:
        for url in PROXY_URLS:  # Note: Using PROXY_URLS (plural) instead of PROXY_URL
            try:
                # Add a random query parameter to bypass caching
                random_query = f"?nocache={int(time.time())}_{random.randint(1, 1000)}"
                url_with_query = url + random_query  # Use url from the loop, not PROXY_URL

                headers = {
                    "User-Agent": random.choice(USER_AGENTS),
                    "Accept": "text/html,application/xhtml+xml,application/xml",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                    "Referer": "https://www.google.com/"
                }
                
                print(f"[INFO] Trying to fetch from {url}...")
                response = requests.get(url_with_query, headers=headers, timeout=15)
                response.raise_for_status()

                # Regular expression to match IP:Port format
                proxy_pattern = r"(\d{1,3}(?:\.\d{1,3}){3}):(\d+)"
                found = re.findall(proxy_pattern, response.text)
                
                if found:
                    print(f"[SUCCESS] Found {len(found)} proxies from {url}")
                    proxies_found.extend(found)
                    successful_sites += 1
                else:
                    print(f"[WARNING] No proxies found on {url}")
                    
                # Add a delay between requests to avoid getting blocked
                time.sleep(random.uniform(2, 4))
                
            except requests.exceptions.RequestException as e:
                print(f"[ERROR] Failed to fetch from {url}: {e}")
                continue
        
        if not proxies_found:
            print("[WARNING] No proxies found from any source.")
            return
        
        # Remove duplicates
        unique_proxies = list(set([f"{p[0]}:{p[1]}" for p in proxies_found]))
        print(f"[INFO] Found {len(unique_proxies)} unique proxies from {successful_sites} sites")
        
        # Apply the limit if specified
        if limit is not None:
            unique_proxies = unique_proxies[:limit]
        
        # Save proxies to a file
        with open(PROXY_FILE, "w") as file:
            for proxy in unique_proxies:
                file.write(f"{proxy}\n")
        
        print(f"[SUCCESS] Saved {len(unique_proxies)} proxies to {PROXY_FILE}")

    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")

if __name__ == "__main__":
    fetch_proxies_with_regex()