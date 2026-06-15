"""SAP Query Tests"""
from app.services.sap_query_service import SAPQueryService

def test_detect_table_scope():
    service = SAPQueryService()
    assert service.detect_table_scope("show sales orders") == 'vbak'
    assert service.detect_table_scope("list items") == 'vbap'
