import random
import threading
import colorama
import requests
import time
import queue
from colorama import Fore, Style
from concurrent.futures import ThreadPoolExecutor

from get_proxy_list import fetch_proxies_with_regex


colorama.init(autoreset=True)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
]

test_urls = [
    "https://httpbin.org/ip",
    "http://httpbin.org/ip"
]


def load_proxies(file_path):
    """
    Load proxy list from a file, formatting them correctly.
    
    Parameters:
        file_path (str): Path to the proxy file.
        
    Returns:
        list: A list of formatted proxy URLs.
    """
    try:
        with open(file_path, "r") as file:
            proxies = [line.strip() for line in file if line.strip()]
        return proxies
    except FileNotFoundError:
        print(f"[ERROR] Proxy file '{file_path}' not found.")
        return []


def test_proxy(proxy, result_queue):
    """
    Test a single proxy by sending a request to httpbin.org/ip.
    
    Parameters:
        proxy (str): Proxy URL in the form "http://ip:port"
        
    Returns:
        dict: Contains proxy, status (True/False), response time, and detected IP.
    """
    proxies = {
        "http": f"http://{proxy}",
        "https": f"https://{proxy}",
    }
    headers = {"User-Agent": random.choice(USER_AGENTS)}    

    for test_url in test_urls:
        try:
            start_time = time.time()
            response = requests.get(test_url, proxies=proxies, timeout=10,headers=headers, verify=False)
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                ip_info = response.json()
                print(f"{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} Proxy {proxy} works! with {test_url} Response time: {elapsed:.2f} sec. Detected IP: {ip_info['origin']}")
                result_queue.put({"proxy": proxy, "status": True, "time": elapsed, "ip": ip_info["origin"]})
            else:
                print(f"{Fore.RED}[FAIL]{Style.RESET_ALL} Proxy {proxy} failed with {test_url} with status code: {response.status_code}")
                result_queue.put({"proxy": proxy, "status": False})

        except Exception as e:
            print(f"{Fore.RED}[FAIL]{Style.RESET_ALL} Proxy {proxy} failed with {test_url}: {str(e)}")
                    # return {"proxy": proxy, "status": False, "time": None, "ip": None}
            result_queue.put({"proxy": proxy, "status": False})
            
    return result_queue.get()

def save_working_proxies(proxies, filename="working_proxies.txt"):
    """
    Save working proxies to a file.
    
    Parameters:
        proxies (list): List of working proxy URLs.
        filename (str): Name of the file to save the proxies.
    """
    with open(filename, "w") as file:
        for proxy in proxies:
            file.write(proxy + "\n")
    print(f"[INFO] Saved {len(proxies)} working proxies to '{filename}'")


def proxy_cheaker():
    """
    Check proxies from the working proxies file first. If none work, fall back to proxies.txt.
    """
    print("Using default proxy file path.")
    working_proxy_file = "database/working_proxies.txt"  # File containing previously working proxies
    proxy_file = "database/proxies.txt"  # File containing all proxies

    # Step 1: Load working proxies from the working proxies file
    print("[INFO] Checking working proxies from 'working_proxies.txt'...")
    working_proxies = load_proxies(working_proxy_file)
    
    if working_proxies:
        print("[INFO] Testing working proxies...")
        result_queue = queue.Queue()

        # Test working proxies
        with ThreadPoolExecutor(max_workers=10) as executor:
            for proxy in working_proxies:
                executor.submit(test_proxy, proxy, result_queue)

        results = []
        while not result_queue.empty():
            results.append(result_queue.get())

        # Filter out valid working proxies
        valid_working_proxies = [r["proxy"] for r in results if r["status"]]

        if valid_working_proxies:
            print(f"[SUCCESS] Found {len(valid_working_proxies)} valid working proxies.")
            print(f"Using these proxies: {valid_working_proxies}")
            
            with open(working_proxy_file, "w") as file:
                for proxy in valid_working_proxies:
                    file.write(proxy + "\n")

            print(f"[INFO] Saved {len(valid_working_proxies)} valid working proxies to '{working_proxy_file}'")
            
            return valid_working_proxies
        else:
            print("[WARNING] No valid working proxies found in 'working_proxies.txt'. Falling back to 'proxies.txt'.")


     # Step 2: Load proxies from proxies.txt if no valid working proxies are found
    print("[INFO] Checking proxies from 'proxies.txt'...")
    fetch_proxies_with_regex(100)
    proxy_list = load_proxies(proxy_file)

    if not proxy_list:
        print("[ERROR] No proxies loaded from 'database/proxies.txt'. Exiting.")
        return []

    result_queue = queue.Queue()

    # Test proxies from proxies.txt
    with ThreadPoolExecutor(max_workers=10) as executor:
        for proxy in proxy_list:
            executor.submit(test_proxy, proxy, result_queue)

    results = []
    while not result_queue.empty():
        results.append(result_queue.get())

    # Filter out valid working proxies
    working_proxies = [r["proxy"] for r in results if r["status"]]

    if working_proxies:
        print(f"[SUCCESS] Found {len(working_proxies)} working proxies.")
        print(f"Using these proxies: {working_proxies}")
        save_working_proxies(working_proxies, working_proxy_file)
    else:
        print("[ERROR] No working proxies found.")

    return working_proxies

if __name__ == "__main__":
    proxy_cheaker()