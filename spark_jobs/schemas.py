"""Explicit phase1-v1 schemas; range/business rules belong to quality assessment."""
from pyspark.sql.types import StructType, StructField, LongType, StringType, DateType, TimestampType, DecimalType

VERSION = "phase1-v1"
CHANNELS = ("Dine-in", "Takeaway", "Website", "App", "Third-Party Delivery")
DEFINITIONS = {
    "Customers": "Customer_ID:L Customer_Name:S City:S Signup_Date:D Preferred_Channel:S",
    "Menu_Categories": "Category_ID:L Category_Name:S",
    "Menu_Items": "Item_ID:L Item_Name:S Category_ID:L Base_Price:M Cost:M Description:S Is_Available:L Introduced_Date:D",
    "Restaurants": "Location_ID:L Location_Name:S City:S Address:S Opening_Date:D",
    "Promotions": "Promotion_ID:L Promotion_Name:S Discount_Percent:L Start_Date:D End_Date:D Applicable_Category_ID:L Applicable_Item_ID:L",
    "Orders": "Order_ID:L Customer_ID:L Location_ID:L Order_DateTime:T Channel:S Promotion_ID:L Order_Status:S",
    "Order_Items": "Order_Item_ID:L Order_ID:L Item_ID:L Quantity:L Unit_Price:M Discount_Applied:M",
    "Pricing_History": "Pricing_ID:L Item_ID:L Price:M Effective_Date:D",
    "Ratings": "Rating_ID:L Order_ID:L Item_ID:L Customer_ID:L Stars:L Rating_Date:T",
    "Inventory": "Inventory_ID:L Location_ID:L Item_ID:L Stock_Quantity:L Reorder_Level:L Last_Restocked_Date:D Opening_Stock:L Received_Quantity:L Consumed_Quantity:L Wasted_Quantity:L Period_Start:D Period_End:D",
    "Wastage": "Wastage_ID:L Item_ID:L Location_ID:L Wastage_Date:D Quantity_Wasted:L Cost_Impact:M Reason:S Demand_Quantity:L Prepared_Quantity:L Quantity_Consumed:L",
}
TYPES = {"L": LongType(), "S": StringType(), "D": DateType(), "T": TimestampType(), "M": DecimalType(18, 2)}
SCHEMAS = {name: StructType([StructField(field, TYPES[kind], True) for field, kind in (part.split(":") for part in spec.split())]) for name, spec in DEFINITIONS.items()}
PK = {name: schema.fieldNames()[0] for name, schema in SCHEMAS.items()}
OPTIONAL = {"Orders": {"Promotion_ID"}}
ENUMS = {("Customers", "Preferred_Channel"): CHANNELS, ("Orders", "Channel"): CHANNELS,
         ("Orders", "Order_Status"): ("Completed", "Cancelled"), ("Menu_Items", "Is_Available"): (0, 1),
         ("Wastage", "Reason"): ("Overproduction", "Spoilage", "Preparation Error", "Customer Return", "Expired Ingredients")}


def required_ids(table):
    return [f.name for f in SCHEMAS[table] if f.name.endswith("_ID") and f.name not in OPTIONAL.get(table, set())]
