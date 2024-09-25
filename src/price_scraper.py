import requests
from bs4 import BeautifulSoup

def price_scraper_function():
    #### Lithium Price Scraper
    # Define the URL you want to scrape
    metals_url = 'https://www.metal.com/Chemical-compound/201102250059'

    # Send a GET request to the webpage
    metals_response = requests.get(metals_url)


    if metals_response.status_code == 200:
        # Parse the page content using BeautifulSoup
        soup = BeautifulSoup(metals_response.content, 'html.parser')
        
        # Find all article titles (the HTML tags might be different based on the structure of the website)
        prices = soup.find_all('div', class_='price___2mpJr')
        date = soup.find('div', class_='date___2tAG6')
        l = []
        # Loop through each title and print it
        for price in prices:
            l.append(float(price.get_text().strip().replace(",", "")))

    #### Exchange Rate Scraper
    # Define the URL you want to scrape
    xchange_url = 'https://www.google.com/finance/quote/USD-CNY?sa=X&ved=2ahUKEwiZtPyy5NuIAxUsweYEHcFTObEQmY0JegQIFBAw'

    # Send a GET request to the webpage
    xchange_response = requests.get(xchange_url)

    if xchange_response.status_code == 200:
        # Parse the page content using BeautifulSoup
        soup = BeautifulSoup(xchange_response.content, 'html.parser')
        
        # Find all article titles (the HTML tags might be different based on the structure of the website)
        xchange = soup.find('div', class_='YMlKec fxKbKc')
        
        l.append(float(xchange.get_text()))

    return l