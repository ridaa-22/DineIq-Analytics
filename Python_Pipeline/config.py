import os

DATASET_VERSION = "v1_1M"
BASE_DIR = "Dineiq_Dataset_RM"

PATHS = {
    "orders": os.path.join(BASE_DIR, "Orders.csv"),
    "order_items": os.path.join(BASE_DIR, "Order_Items.csv"),
    "customers": os.path.join(BASE_DIR, "Customers.csv"),
    "menu_items": os.path.join(BASE_DIR, "Menu_Items.csv"),
    "menu_categories": os.path.join(BASE_DIR, "Menu_Categories.csv"),
    "restaurants": os.path.join(BASE_DIR, "Restaurants.csv"),
    "promotions": os.path.join(BASE_DIR, "Promotions.csv"),
    "ratings": os.path.join(BASE_DIR, "Ratings.csv"),
    "inventory": os.path.join(BASE_DIR, "Inventory.csv"),
    "wastage": os.path.join(BASE_DIR, "Wastage.csv"),
    "pricing_history": os.path.join(BASE_DIR, "Pricing_History.csv"),
}

REPORTS_DIR = "reports"
MODELS_DIR = "models/python"

os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)

print("Config loaded. Dataset version:", DATASET_VERSION)