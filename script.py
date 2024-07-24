from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

import csv

import re
import pandas as pd

# Define a function to check if a URL is a Google Maps URL
def is_google_maps_url(url):
    return isinstance(url, str) and 'google.com/maps' in url

# Define a function to consolidate Google Maps link
def consolidate_google_maps_link(row):
    if is_google_maps_url(row['google maps link']):
        return row['google maps link']
    elif is_google_maps_url(row['website']):
        return row['website']
    else:
        return None
    

def extract_lat_lng(url):
    if not isinstance(url, str):
        return None, None
    match = re.search(r'!3d([-0-9.]+)!4d([-0-9.]+)', url)
    if match:
        lat = match.group(1)
        lng = match.group(2)
        return float(lat), float(lng)
    else:
        return None, None
    

def get_scrape_function():
    return """
    function scrapeData() {
        var links = Array.from(document.querySelectorAll('a[href^="https://www.google.com/maps/place"]'));
        return links.map(link => {
            var container = link.closest('[jsaction*="mouseover:pane"]');
            var titleText = container ? container.querySelector('.fontHeadlineSmall').textContent : '';
            var rating = '';
            var reviewCount = '';
            var phone = '';
            var industry = '';
            var address = '';
            var companyUrl = '';

            // Rating and Reviews
            if (container) {
                var roleImgContainer = container.querySelector('[role="img"]');
                
                if (roleImgContainer) {
                    var ariaLabel = roleImgContainer.getAttribute('aria-label');
                
                    if (ariaLabel && ariaLabel.includes("stars")) {
                        var parts = ariaLabel.split(' ');
                        var rating = parts[0];
                        var reviewCount = parts[2]; 
                    } else {
                        rating = '0';
                        reviewCount = '0';
                    }
                }
            }

            // Address and Industry
            if (container) {
                var containerText = container.textContent || '';
                var addressRegex = /\\d+ [\\w\\s]+(?:#\\s*\\d+|Suite\\s*\\d+|Apt\\s*\\d+)?/;
                var addressMatch = containerText.match(addressRegex);

                if (addressMatch) {
                    address = addressMatch[0];

                    var textBeforeAddress = containerText.substring(0, containerText.indexOf(address)).trim();
                    var ratingIndex = textBeforeAddress.lastIndexOf(rating + reviewCount);
                    if (ratingIndex !== -1) {
                        var rawIndustryText = textBeforeAddress.substring(ratingIndex + (rating + reviewCount).length).trim().split(/[\\r\\n]+/)[0];
                        industry = rawIndustryText.replace(/[·.,#!?]/g, '').trim();
                    }
                    var filterRegex = /\\b(Closed|Open 24 hours|24 hours)|Open\\b/g;
                    address = address.replace(filterRegex, '').trim();
                    address = address.replace(/(\\d+)(Open)/g, '$1').trim();
                    address = address.replace(/(\\w)(Open)/g, '$1').trim();
                    address = address.replace(/(\\w)(Closed)/g, '$1').trim();
                } else {
                    address = '';
                }
            }

            // Company URL
            if (container) {
                var allLinks = Array.from(container.querySelectorAll('a[href]'));
                var filteredLinks = allLinks.filter(a => !a.href.startsWith("https://www.google.com/maps/place/"));
                if (filteredLinks.length > 0) {
                    companyUrl = filteredLinks[0].href;
                }
            }

            // Phone Numbers
            if (container) {
                var containerText = container.textContent || '';
                var phoneRegex = /(\\+\\d{1,2}\\s)?\\(?\\d{3}\\)?[\\s.-]?\\d{3}[\\s.-]?\\d{4}/;
                var phoneMatch = containerText.match(phoneRegex);
                phone = phoneMatch ? phoneMatch[0] : '';
            }

            return {
                Title: titleText,
                Rating: rating,
                Reviews: reviewCount,
                Phone: phone,
                Industry: industry,
                Address: address,
                Website: companyUrl,
                'Google Maps Link': link.href,
            };
        });
    }
    return scrapeData();
    """

def wait_for_results_container(driver, xpath, timeout=20):
    try:
        return WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )
    except Exception as e:
        print(f"An error occurred while waiting for the results container: {e}")
        return None

def scrape_data(driver):
    script = get_scrape_function()
    return driver.execute_script(script)

def save_to_csv(data, filename='google_maps_data.csv'):
    # Define the column order to match the extension's output
    columns = ['Title', 'Rating', 'Reviews', 'Phone', 'Industry', 'Address', 'Website', 'Google Maps Link']
    
    with open(filename, 'w', newline='', encoding='utf-8') as output_file:
        writer = csv.DictWriter(output_file, fieldnames=columns)
        writer.writeheader()
        for row in data:
            writer.writerow({k: row.get(k, '') for k in columns})
    print(f"Data saved to {filename}")

def scroll_results_container(driver, results_container, max_scroll_attempts=200, scroll_delay=0.5):
    last_height = driver.execute_script("return arguments[0].scrollHeight", results_container)
    print(f"Initial scroll height: {last_height}")
    
    attempts = 0
    no_change_count = 0
    while attempts < max_scroll_attempts:
        try:
            # Scroll down to bottom
            driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", results_container)
            
            # Wait to load page
            time.sleep(scroll_delay)
            
            # Calculate new scroll height and compare with last scroll height
            new_height = driver.execute_script("return arguments[0].scrollHeight", results_container)
            
            if new_height == last_height:
                no_change_count += 1
                if no_change_count >= 10:  # If no change for 10 consecutive attempts, stop scrolling
                    print("No more new results loaded after multiple attempts.")
                    break
            else:
                no_change_count = 0  # Reset the counter if there's a change
            
            last_height = new_height
            attempts += 1
            
            # Print progress every 10 attempts
            if attempts % 10 == 0:
                print(f"Scroll attempt {attempts}, current height: {new_height}")
            
        except Exception as e:
            print(f"An error occurred during scrolling: {e}")
            break

    if attempts >= max_scroll_attempts:
        print(f"Reached maximum scroll attempts ({max_scroll_attempts}). Results may be incomplete.")
    else:
        print(f"Scrolling completed after {attempts} attempts.")

    # Final scroll to top
    driver.execute_script("arguments[0].scrollTop = 0", results_container)



search_query = 'restaurants and cafes in New Cairo'

# Path to ChromeDriver
chrome_driver_path = '/usr/local/bin/chromedriver'

# Set up ChromeDriver service
service = Service(chrome_driver_path)

# Set up Chrome options
chrome_options = Options()

# Use the existing Chrome profile
user_data_dir = "/Users/omarmagdy/Library/Application Support/Google/Chrome"
profile_directory = "Profile 1"  # Use your specific profile directory

chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
chrome_options.add_argument(f"--profile-directory={profile_directory}")

chrome_options.add_argument("--start-maximized")  # Maximize window
chrome_options.add_argument("--disable-gpu")  # Disable GPU

# Optional: specify the Chrome binary location
chrome_options.binary_location = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

# Create the WebDriver instance
driver = webdriver.Chrome(service=service, options=chrome_options)



try:
    # Open Google Maps
    driver.get("https://www.google.com/maps")
    
    # Wait for the page to load
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.ID, "searchboxinput"))
    )

    # Find the search input element by its ID
    search_box = driver.find_element(By.ID, "searchboxinput")

    # Type the search query into the search box
   
    search_box.send_keys(search_query)

    # Submit the search form
    search_box.send_keys(Keys.RETURN)  # This simulates pressing the Enter key

    # Wait for the search results container to be available
    results_xpath = f"//div[contains(@aria-label, '{search_query}')]"
    results_container = wait_for_results_container(driver, results_xpath)

    if results_container:
        # Scroll the search results container until no more results are loaded
        scroll_results_container(driver, results_container, max_scroll_attempts=200, scroll_delay=0.8)
        # Click the extension
        scraped_data = scrape_data(driver)
        
        # Save the data to CSV
        save_to_csv(scraped_data)

        df = pd.read_csv('google_maps_data.csv', encoding='utf-8')
        df = df.drop(['Phone', 'Industry', 'Address'], axis=1)
        df.columns = df.columns.str.lower()
        # Apply the function to create the new column
        df['url'] = df.apply(consolidate_google_maps_link, axis=1)
        # Drop the old columns if you no longer need them
        df = df.drop(columns=['google maps link', 'website'])

        df['url'] = df['url'].astype(str)

        # Apply the extraction function to each URL
        df[['latitude', 'longitude']] = df['url'].apply(lambda x: pd.Series(extract_lat_lng(x)))

        #rename title to name 
        df = df.rename(columns={'title': 'name'})
        #drop duplicates
        df = df.drop_duplicates()
        df.to_excel(f'{search_query}.xlsx', index=False)

        print(f"Scraped {len(scraped_data)} results.")
    else:
        print("Results container was not found.")       
 
    # Optional: Add any additional actions or interactions here

    # Keep the browser open
    print("The browser will remain open. Close it manually when done.")

    # Keep the script running until the user closes the browser
    input("Press Enter to exit and close the browser...")

except Exception as e:
    print(f"An error occurred: {e}")

finally:
    # Close the browser (only when the user presses Enter)
    driver.quit()