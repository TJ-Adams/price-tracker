#!/usr/bin/env python3
import sys,json, requests, bs4
from twilio.rest import Client
from price_parser import Price
from twilio_pass import *


PRODUCTS_FILE = "products.json"

def print_help():
    print('Usage: {} <command>'.format(sys.argv[0]))
    print()
    print('command:')
    print('  remove              choose products to stop tracking')
    print('  add                 add product to start tracking')
    print('  edit                change product options')
    print('  show                displays product information to stdout')
    print('  run                 gets current price and sends text if requirements met')
    print('  force-text          gets current price and sends text')

def list_products( products_file ):
    """
    List all the products that are currently being tracked.
    Displays only name and index of product starting at 0.
    """
    # Parse JSON Products to list products
    with open(products_file) as f:
        data = json.load(f)

    # List Products to remove
    print('INDEX        PRODUCT NAME')
    for num,product in enumerate(data['products']):
        print('{}            {}'.format(num,product['name']))

def show_product_info():
    """
    show the product info listed in the json file to stdout
    """
    try:
        with open(PRODUCTS_FILE) as f:
            data = json.load(f)
    except:
        print("Not tracking any products. Run ./check_price.py add")
        return

    print('NAME            LAST_PRICE                TARGET_PRICE')
    for product in data['products']:
        print('{}    {:<8.2f}                  {}'.format(product['name'][:12], product['current_price'], product['target_price']))

def add_product():
    """
    Gets relevant product information through user prompts in
    order to add product to list of products to track.
    """
    # Grab relevant product information
    name = input('Name of the Product: ')
    url  = input('URL of Product: ')
    price_tag_type = input('Type of element holding the price? <div, span, etc>: ')
    price_identifier = input('class=(without quotation marks): ')
    currency_tag_type = input('Type of element holding the currency? <div, span, etc>: ')
    currency_identifier = input('class=(without quotation marks): ')
    target_price = float(input('Target price (Just whole number without commas etc) <=: '))

    # Create JSON Element for Product
    product_json = { "name": name, "url": url, "price_tag_type": price_tag_type,
        "price_identifier": price_identifier, "currency_tag_type": currency_tag_type,
        "currency_identifier": currency_identifier, "target_price": target_price,
        "current_price": target_price+1}

    # Append JSON Element to end of list
    with open(PRODUCTS_FILE) as f:
        data = json.load(f)
        data['products'].append(product_json)

    with open(PRODUCTS_FILE, 'w') as f:
        json.dump(data,f)

    print('Succesfully added "{}" to list of tracked products!'.format(name))

def remove_product():
    """
    Allow user to pick a product to stop tracking.
    """
    try:
        open(PRODUCTS_FILE)
    except:
        print('Cannot open {}'.format(PRODUCTS_FILE))

    list_products(PRODUCTS_FILE)
    remove_idx = int(input('\nIndex of product to remove: '))

    with open(PRODUCTS_FILE) as f:
        data = json.load(f)

    product_name = data['products'][remove_idx]['name']
    del data['products'][remove_idx]

    with open(PRODUCTS_FILE, 'w') as f:
        json.dump(data, f)

    print('Succesfully stopped tracking {}'.format(product_name))

def edit_product():
    list_products(PRODUCTS_FILE)
    change_idx = int(input('Index of product to update: '))

    with open(PRODUCTS_FILE) as f:
        data = json.load(f)

    print('PARAMETERS:')
    print('  name')
    print('  url')
    print('  price_tag_type')
    print('  price_identifier')
    print('  currency_tag_type')
    print('  currency_identifier')
    print('  target_price')

    change_param = input('Parameter to change: ')
    print('Old parameter value: {}'.format(data['products'][change_idx][change_param]))
    new_param_val = input('New Value for Parameter: ')
    data['products'][change_idx][change_param] = new_param_val

    with open(PRODUCTS_FILE, 'w') as f:
        json.dump(data, f)

    print('Successfully edited product information')


def run_check(force_text):
    """
    Look at the list of products and grab relevant information and send text message
    if requirements are met
    """

    with open(PRODUCTS_FILE) as f:
        data = json.load(f)

    # Set variables for Scraping
    user_agent = 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:74.0) Gecko/20100101 Firefox/74.0'
    headers = {'User-Agent': user_agent}
    message_body = ''
    price_changed = False

    for idx, product in enumerate(data['products']):
        print('Getting HTML...')
        try:
            res = requests.get(product['url'], headers=headers)
        except:
            print('Error occurred in attempting to get html for {}'.format(product['url']))
            message_body += ('Failed to get page {} for {}\n'.format(product['url'], product['name']))
            continue

        if res.raise_for_status() != None:
            print('Error occurred in attempting to get URL')
            message_body += ('Failed to get page {} for {}\n'.format(product['url'], product['name']))
            continue

        soup = bs4.BeautifulSoup(res.text, 'html.parser')

        # Grab Price
        price_soup = soup.findAll(product['price_tag_type'], class_=product['price_identifier'] )
        if len(price_soup) == 0:
            message_body += 'Could not get product info for {}.'.format(product['name'])
            continue

        new_price = Price.fromstring(price_soup[0].text)

        old_price = data['products'][idx]['current_price']
        # Check if there are any price updates
        if float(new_price.amount) != float(old_price):
            price_changed = True
            data['products'][idx]['current_price'] = float(new_price.amount)

        if new_price.currency == None:
            new_price.currency = soup.findAll(product['currency_tag_type'], class_=product['currency_identifier'])[0].text
        message_body += '{} costs {}{}. Old Price: {}{}\n\n'.format(product['name'], new_price.currency, new_price.amount, new_price.currency, old_price)

    with open(PRODUCTS_FILE,'w') as f:
        json.dump(data,f)

    if force_text == True or price_changed == True:
        # Get text message client
        print('Getting Twilio Client...')
        twilioCli = Client(ACCOUNTSID, AUTHTOKEN)

        # Send Message
        message = twilioCli.messages.create(body=message_body, from_=TWILIONUMBER, to=CELLPHONE)
        print('Message Queued!')


# Check Command Line Arguments
if len(sys.argv) == 2:
    if sys.argv[1] == '--help':
        print_help()
    elif sys.argv[1] == 'remove':
        remove_product()
    elif sys.argv[1] == 'add':
        add_product()
    elif sys.argv[1] == 'edit':
        edit_product()
    elif sys.argv[1] == 'show':
        show_product_info()
    elif sys.argv[1] == 'run':
        run_check(False)
    elif sys.argv[1] == 'force-text':
        run_check(True)
    else:
        print_help()
else:
    print_help()


