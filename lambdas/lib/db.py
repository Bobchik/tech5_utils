import os
import yaml


DATABASE_DIR = os.path.join(os.path.dirname(__file__), '../database')
CUSTOMERS_DIR = os.path.join(DATABASE_DIR, 'customers')


def load_employees():
    config = os.path.join(DATABASE_DIR, 'employees.yaml')
    if not os.path.exists(config):
        raise ValueError("Employee file is not available")
    with open(config, 'r') as yfile:
        employees = yaml.load(yfile, Loader=yaml.FullLoader)
    return employees


def load_employee_by_nickname(nickname):
    employees = load_employees()
    for e in employees:
        if e.get('nickname') == nickname:
            return e
    raise ValueError(f"Employee {nickname} was not found")


def load_employee_by_email(email):
    employees = load_employees()
    for e in employees:
        if e.get('private_email') == email:
            return e
        elif e.get('work_email') == email:
            return e
    raise ValueError(f"Employee {email} was not found")


def load_customer(customer_name):
    customer_config = os.path.join(CUSTOMERS_DIR, customer_name + '.yaml')
    if os.path.exists(customer_config):
        with open(customer_config, 'r') as yfile:
            customer = yaml.load(yfile, Loader=yaml.FullLoader)
    else:
        customer = load_customer_by_shortname(customer_name)
    return customer


def load_customer_by_shortname(customer_name):
    """Loads all customer configs and finds a customer by short_name"""
    for filename in os.listdir(CUSTOMERS_DIR):
        customer_config = os.path.join(CUSTOMERS_DIR, filename)
        with open(customer_config, 'r') as yfile:
            customer = yaml.load(yfile, Loader=yaml.FullLoader)
            if customer.get('short_name') == customer_name:
                return customer
    raise ValueError(f"Customer {customer_name} is not in customer list")
