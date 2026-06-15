from hdbcli import dbapi

conn = dbapi.connect(
    address='172.16.15.10',
    port=30015,
    user='READ_ONLY_1',
    password='Primus@321'
)
cursor = conn.cursor()

# Test 1 - SYS.COLUMNS metadata
try:
    cursor.execute("""
        SELECT COLUMN_NAME, COMMENTS, DATA_TYPE_NAME
        FROM SYS.COLUMNS 
        WHERE SCHEMA_NAME = 'SAPHANADB' AND TABLE_NAME = 'VBAK'
        LIMIT 5
    """)
    print('✅ SYS.COLUMNS:', cursor.fetchall())
except Exception as e:
    print(f'❌ SYS.COLUMNS: {e}')

# Test 2 - AUART distinct values
try:
    cursor.execute('SELECT DISTINCT AUART, COUNT(*) FROM "SAPHANADB"."VBAK" GROUP BY AUART')
    print('✅ AUART values:', cursor.fetchall())
except Exception as e:
    print(f'❌ AUART: {e}')

# Test 3 - KUNNR format
try:
    cursor.execute('SELECT DISTINCT KUNNR FROM "SAPHANADB"."VBAK" LIMIT 5')
    print('✅ KUNNR format:', cursor.fetchall())
except Exception as e:
    print(f'❌ KUNNR: {e}')

# Test 4 - LIFNR format
try:
    cursor.execute('SELECT DISTINCT LIFNR FROM "SAPHANADB"."EKKO" LIMIT 5')
    print('✅ LIFNR format:', cursor.fetchall())
except Exception as e:
    print(f'❌ LIFNR: {e}')

# Test 5 - ARKTX in VBAP
try:
    cursor.execute('SELECT DISTINCT ARKTX FROM "SAPHANADB"."VBAP" LIMIT 5')
    print('✅ ARKTX values:', cursor.fetchall())
except Exception as e:
    print(f'❌ ARKTX: {e}')

conn.close()