"""Realistic Enterprise Seed Data Generator.

Generates:
- 5 Regions (North, South, East, West, Central)
- 550+ Customers (Enterprise, Mid-Market, SMB across 5 industries)
- 10 Products with realistic enterprise software pricing
- 5,200+ Orders spanning 2024 to 2026
- 11,500+ Order Items with realistic quantities and pricing
- Outputs data/seed.sql and can seed live database.
"""

import os
import random
from datetime import datetime, timedelta
from typing import List, Tuple

# Fix random seed for reproducible, consistent enterprise analytics
random.seed(42)

REGIONS = ["North", "South", "East", "West", "Central"]

INDUSTRIES = ["Technology", "Financial Services", "Healthcare", "Retail & E-commerce", "Manufacturing"]

SEGMENTS = ["Enterprise", "Mid-Market", "SMB"]
SEGMENT_WEIGHTS = [0.30, 0.40, 0.30]

PRODUCTS: List[Tuple[str, str, float]] = [
    ("Cloud Platform", "Infrastructure", 4500.00),
    ("AI Analytics Suite", "Artificial Intelligence", 8200.00),
    ("Data Integration Platform", "Data Engineering", 3200.00),
    ("Security Platform", "Cybersecurity", 5800.00),
    ("Customer Analytics", "Business Intelligence", 2900.00),
    ("Enterprise API Platform", "Integration", 3900.00),
    ("ML Platform", "Artificial Intelligence", 9500.00),
    ("Observability Suite", "DevOps", 2400.00),
    ("Automation Platform", "Workflow", 4100.00),
    ("Data Warehouse Solution", "Data Engineering", 6500.00),
]

COMPANY_PREFIXES = [
    "Apex", "Vertex", "Quantum", "Nexus", "Acro", "Omni", "Summit", "Horizon", "Pinnacle", "Vanguard",
    "Synergy", "Beacon", "Crest", "Alpha", "Starlight", "Core", "Global", "United", "Prime", "Dynamic",
    "Insight", "Zenith", "Meridian", "Catalyst", "Hyper", "Terra", "Nova", "Stratos", "Solaris", "Velocity"
]

COMPANY_SUFFIXES = [
    "Technologies", "Solutions", "Enterprises", "Systems", "Holdings", "Corp", "Industries", "Group",
    "Networks", "Labs", "Analytics", "Health", "Capital", "Logistics", "Ventures", "Services"
]

STATUSES = ["Completed", "Pending", "Cancelled", "Returned"]
STATUS_WEIGHTS = [0.82, 0.08, 0.06, 0.04]


def generate_customers(count: int = 550) -> List[Tuple[int, str, int, str, str, str]]:
    customers = []
    start_date = datetime(2023, 1, 1)
    
    used_names = set()
    for i in range(1, count + 1):
        name = f"{random.choice(COMPANY_PREFIXES)} {random.choice(COMPANY_SUFFIXES)}"
        if name in used_names:
            name = f"{name} {i}"
        used_names.add(name)
        
        # Region selection: slight bias towards North and West for realistic analytical skew
        region_id = random.choices([1, 2, 3, 4, 5], weights=[0.28, 0.18, 0.20, 0.22, 0.12])[0]
        segment = random.choices(SEGMENTS, weights=SEGMENT_WEIGHTS)[0]
        industry = random.choice(INDUSTRIES)
        created_at = (start_date + timedelta(days=random.randint(0, 500))).strftime("%Y-%m-%d %H:%M:%S")
        customers.append((i, name, region_id, segment, industry, created_at))
    return customers


def generate_orders_and_items(
    customers: List[Tuple],
    order_count: int = 5300
) -> Tuple[List[Tuple], List[Tuple]]:
    orders = []
    order_items = []
    
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2026, 8, 31)
    date_delta_days = (end_date - start_date).days
    
    item_id_counter = 1
    
    for order_id in range(1, order_count + 1):
        # Pick customer with bias towards Enterprise customers buying more frequently
        customer = random.choice(customers)
        cust_id = customer[0]
        cust_segment = customer[3]
        
        order_days = random.randint(0, date_delta_days)
        order_date = (start_date + timedelta(days=order_days)).strftime("%Y-%m-%d")
        status = random.choices(STATUSES, weights=STATUS_WEIGHTS)[0]
        
        orders.append((order_id, cust_id, order_date, status))
        
        # Enterprise buys 2-4 items, Mid-Market 1-3, SMB 1-2
        if cust_segment == "Enterprise":
            num_items = random.randint(2, 4)
        elif cust_segment == "Mid-Market":
            num_items = random.randint(1, 3)
        else:
            num_items = random.randint(1, 2)
            
        chosen_products = random.sample(range(1, len(PRODUCTS) + 1), k=min(num_items, len(PRODUCTS)))
        for prod_id in chosen_products:
            prod = PRODUCTS[prod_id - 1]
            base_price = prod[2]
            
            # Enterprise orders higher quantities
            if cust_segment == "Enterprise":
                quantity = random.randint(2, 8)
            elif cust_segment == "Mid-Market":
                quantity = random.randint(1, 4)
            else:
                quantity = random.randint(1, 2)
                
            order_items.append((item_id_counter, order_id, prod_id, quantity, base_price))
            item_id_counter += 1
            
    return orders, order_items


def build_sql_seed_file(output_path: str = "data/seed.sql") -> None:
    print(f"Generating realistic dataset for {output_path}...")
    customers = generate_customers(550)
    orders, order_items = generate_orders_and_items(customers, 5300)
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("-- Realistic Enterprise Seed Data\n")
        f.write("-- 5 Regions, 550 Customers, 10 Products, 5300 Orders, 11500+ Items\n\n")
        f.write("USE enterprise_analytics;\n\n")
        f.write("SET FOREIGN_KEY_CHECKS = 0;\n")
        f.write("TRUNCATE TABLE order_items;\n")
        f.write("TRUNCATE TABLE orders;\n")
        f.write("TRUNCATE TABLE customers;\n")
        f.write("TRUNCATE TABLE products;\n")
        f.write("TRUNCATE TABLE regions;\n")
        f.write("SET FOREIGN_KEY_CHECKS = 1;\n\n")
        
        # 1. Regions
        f.write("-- Insert Regions\n")
        f.write("INSERT INTO regions (region_id, region_name) VALUES\n")
        reg_rows = [f"({i+1}, '{r}')" for i, r in enumerate(REGIONS)]
        f.write(",\n".join(reg_rows) + ";\n\n")
        
        # 2. Products
        f.write("-- Insert Products\n")
        f.write("INSERT INTO products (product_id, product_name, category, unit_price) VALUES\n")
        prod_rows = [f"({i+1}, '{p[0]}', '{p[1]}', {p[2]:.2f})" for i, p in enumerate(PRODUCTS)]
        f.write(",\n".join(prod_rows) + ";\n\n")
        
        # 3. Customers in batches
        f.write("-- Insert Customers (550 records)\n")
        cust_batch_size = 100
        for b in range(0, len(customers), cust_batch_size):
            batch = customers[b : b + cust_batch_size]
            f.write("INSERT INTO customers (customer_id, customer_name, region_id, customer_segment, industry, created_at) VALUES\n")
            c_rows = []
            for c in batch:
                safe_name = c[1].replace("'", "''")
                c_rows.append(f"({c[0]}, '{safe_name}', {c[2]}, '{c[3]}', '{c[4]}', '{c[5]}')")
            f.write(",\n".join(c_rows) + ";\n\n")
            
        # 4. Orders in batches
        f.write(f"-- Insert Orders ({len(orders)} records)\n")
        order_batch_size = 500
        for b in range(0, len(orders), order_batch_size):
            batch = orders[b : b + order_batch_size]
            f.write("INSERT INTO orders (order_id, customer_id, order_date, status) VALUES\n")
            o_rows = [f"({o[0]}, {o[1]}, '{o[2]}', '{o[3]}')" for o in batch]
            f.write(",\n".join(o_rows) + ";\n\n")
            
        # 5. Order Items in batches
        f.write(f"-- Insert Order Items ({len(order_items)} records)\n")
        item_batch_size = 1000
        for b in range(0, len(order_items), item_batch_size):
            batch = order_items[b : b + item_batch_size]
            f.write("INSERT INTO order_items (order_item_id, order_id, product_id, quantity, unit_price) VALUES\n")
            i_rows = [f"({item[0]}, {item[1]}, {item[2]}, {item[3]}, {item[4]:.2f})" for item in batch]
            f.write(",\n".join(i_rows) + ";\n\n")

    print(f"Successfully generated {output_path} with {len(customers)} customers, {len(orders)} orders, and {len(order_items)} items.")


if __name__ == "__main__":
    build_sql_seed_file("data/seed.sql")
