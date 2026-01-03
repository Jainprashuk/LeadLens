from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import re
from selenium.common.exceptions import ElementClickInterceptedException, NoSuchElementException
from urllib.parse import urlparse, parse_qs, unquote


def _valid_website_href(href: str) -> bool:
    if not href or not href.startswith("http"):
        return False
    try:
        parsed = urlparse(href)
        domain = parsed.netloc.lower()
    except Exception:
        return False

    blacklist = [
        "google.com",
        "googleusercontent.com",
        "gstatic.com",
        "fonts.gstatic.com",
        "accounts.google.com",
        "ggpht.com",
        "googleapis.com",
        "doubleclick.net",
        "g.co",
    ]
    for b in blacklist:
        if b in domain:
            return False

    if any(href.lower().endswith(ext) for ext in ('.woff', '.woff2', '.ttf', '.svg', '.css', '.js')):
        return False

    return True


def extract_website_from_google_redirect(href: str) -> str:
    """Extract actual URL from Google redirect link"""
    if not href:
        return None
    
    parsed = urlparse(href)
    
    # Handle Google redirect URLs like /url?q=http://example.com
    if 'google.com' in parsed.netloc and parsed.path.startswith('/url'):
        qs = parse_qs(parsed.query)
        q = qs.get('q')
        if q:
            return unquote(q[0])
    
    return href


def scrape_google_maps(search_query, scrolls=5):
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    search_url = f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}"
    driver.get(search_url)
    time.sleep(5)

    results = []

    # Scroll results panel
    try:
        scrollable_div = driver.find_element(By.XPATH, "//div[@role='feed']")
        for _ in range(scrolls):
            driver.execute_script(
                "arguments[0].scrollTop = arguments[0].scrollHeight",
                scrollable_div
            )
            time.sleep(3)
    except:
        print("⚠️ Scroll container not found")

    cards = driver.find_elements(By.CLASS_NAME, "Nv2PK")
    print(f"Found {len(cards)} business cards")

    for idx, card in enumerate(cards, 1):
        # Initialize ALL variables for THIS iteration
        website = None
        phone = None
        address = None
        rating = None
        reviews = None
        
        try:
            text = card.text.split("\n")
            name = text[0]
            category = text[1] if len(text) > 1 else ""

            print(f"\n[{idx}/{len(cards)}] Processing: {name}")
            has_website = "Website" in card.text

            # Extract rating & reviews from card text
            for line in text:
                match = re.match(r"(\d\.\d)\((\d+)\)", line)
                if match:
                    rating = float(match.group(1))
                    reviews = int(match.group(2))
                    break

            # Click card to open detail panel
            try:
                driver.execute_script("arguments[0].scrollIntoView(true);", card)
                time.sleep(0.5)
                try:
                    card.click()
                except ElementClickInterceptedException:
                    driver.execute_script("arguments[0].click();", card)
                
                # Wait for detail panel to fully load
                time.sleep(2.5)

                # METHOD 1: Look for the website button with data-item-id="authority"
                try:
                    website_element = driver.find_element(
                        By.XPATH, 
                        "//a[@data-item-id='authority']"
                    )
                    href = website_element.get_attribute('href')
                    if href:
                        website = extract_website_from_google_redirect(href)
                        if website and _valid_website_href(website):
                            print(f"  ✓ Website (method 1): {website}")
                except NoSuchElementException:
                    print(f"  ⚠️ No website button with data-item-id='authority' found")

                # METHOD 2: If method 1 fails, look for buttons with specific aria-labels
                if not website:
                    try:
                        buttons = driver.find_elements(
                            By.XPATH,
                            "//button[contains(@aria-label, 'Website') or .//div[contains(text(), 'Website')]]"
                        )
                        for button in buttons:
                            # The actual link might be in a sibling or parent element
                            parent = button.find_element(By.XPATH, "..")
                            links = parent.find_elements(By.TAG_NAME, "a")
                            for link in links:
                                href = link.get_attribute('href')
                                if href:
                                    candidate = extract_website_from_google_redirect(href)
                                    if candidate and _valid_website_href(candidate):
                                        website = candidate
                                        print(f"  ✓ Website (method 2): {website}")
                                        break
                            if website:
                                break
                    except Exception as e:
                        print(f"  ⚠️ Method 2 failed: {e}")

                # METHOD 3: Look for any link in the main panel that's a valid website
                if not website:
                    try:
                        main_panel = driver.find_element(By.XPATH, "//div[@role='main']")
                        links = main_panel.find_elements(By.TAG_NAME, "a")
                        
                        for link in links:
                            href = link.get_attribute('href')
                            if href:
                                candidate = extract_website_from_google_redirect(href)
                                if candidate and _valid_website_href(candidate):
                                    website = candidate
                                    print(f"  ✓ Website (method 3): {website}")
                                    break
                    except Exception as e:
                        print(f"  ⚠️ Method 3 failed: {e}")

                # Extract phone number
                try:
                    phone_buttons = driver.find_elements(
                        By.XPATH,
                        "//button[contains(@aria-label, 'Phone') or @data-item-id='phone:tel:' or contains(@data-item-id, 'phone')]"
                    )
                    if phone_buttons:
                        phone_text = phone_buttons[0].get_attribute('aria-label')
                        if phone_text:
                            # Extract just the number
                            phone_match = re.search(r"[\d\s\+\-\(\)]{8,}", phone_text)
                            if phone_match:
                                phone = phone_match.group(0).strip()
                                print(f"  ✓ Phone: {phone}")
                except Exception as e:
                    print(f"  ⚠️ Phone extraction failed: {e}")

                # Extract address
                try:
                    address_buttons = driver.find_elements(
                        By.XPATH,
                        "//button[@data-item-id='address']"
                    )
                    if address_buttons:
                        address = address_buttons[0].get_attribute('aria-label')
                        if address and address.startswith('Address: '):
                            address = address.replace('Address: ', '')
                        print(f"  ✓ Address: {address}")
                except Exception:
                    pass

            except Exception as e:
                print(f"  ❌ Failed to extract details: {e}")

            results.append({
                "business_name": name,
                "category": category,
                "rating": rating,
                "reviews": reviews,
                "has_website": has_website,
                "website": website,
                "phone": phone,
                "address": address
            })

        except Exception as e:
            print(f"  ❌ Error processing card: {e}")
            continue

    driver.quit()
    return results