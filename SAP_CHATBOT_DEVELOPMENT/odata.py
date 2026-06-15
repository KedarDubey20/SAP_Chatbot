from app.services.odata_service import odata_service

# Test 1 — basic fetch
records = odata_service.fetch(top=5, select=["SalesOrder", "SoldToParty", "TotalNetAmount", "TransactionCurrency"])
print(records)

# Test 2 — top customers
top_customers = odata_service._execute_aggregation(
    select=["SoldToParty", "TotalNetAmount", "TransactionCurrency"],
    filter_str=None,
    aggregate={"type": "group_by", "group_by": "SoldToParty", "field": "TotalNetAmount", "limit": 5}
)
print(top_customers)

# Test 3 — total sales value
total = odata_service._execute_aggregation(
    select=["TotalNetAmount", "TransactionCurrency"],
    filter_str=None,
    aggregate={"type": "sum", "field": "TotalNetAmount"}
)
print(total)