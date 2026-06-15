from hdbcli import dbapi

conn = dbapi.connect(
    address='172.16.15.10',
    port=30015,
    user='READ_ONLY_1',
    password='Primus@321'
)

cursor = conn.cursor()

query = """
SELECT 
    TABLE_NAME,
    COLUMN_NAME,
    REFERENCED_TABLE_NAME,
    REFERENCED_COLUMN_NAME
FROM SYS.REFERENTIAL_CONSTRAINTS
WHERE SCHEMA_NAME = 'SAPHANADB'
AND TABLE_NAME IN (
    'VBAK',
    'VBAP',
    'KNA1',
    'MARA',
    'EKKO',
    'EKPO',
    'VBEP'
)
"""

cursor.execute(query)

rows = cursor.fetchall()

print("Relationships found:", len(rows))

for r in rows:
    print(r)

conn.close()