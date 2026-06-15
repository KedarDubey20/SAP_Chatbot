#!/usr/bin/env python3
"""
SAP AI Assistant - Comprehensive Test Script
Tests all endpoints with real SAP data
"""

import requests
import json
from pathlib import Path

BASE_URL = "http://localhost:8000"

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def test_health():
    print_section("1. Health Check")
    r = requests.get(f"{BASE_URL}/health/")
    print(f"Status: {r.status_code}")
    print(json.dumps(r.json(), indent=2))
    assert r.status_code == 200

def test_status():
    print_section("2. System Status")
    r = requests.get(f"{BASE_URL}/health/status")
    print(json.dumps(r.json(), indent=2))
    assert r.status_code == 200

def test_schema():
    print_section("3. Get Schema")
    r = requests.get(f"{BASE_URL}/sap/schema")
    data = r.json()
    print(f"Tables loaded: {len(data['tables'])}")
    for table in data['tables']:
        cols = len(data['schema'][table])
        print(f"  - {table}: {cols} columns")
    return data

def test_upload_excel():
    print_section("4. Upload Excel (Optional)")
    
    # Check if sample files exist
    data_dir = Path("data")
    if data_dir.exists():
        for file in data_dir.glob("*.xlsx"):
            print(f"\nUploading {file.name}...")
            with open(file, 'rb') as f:
                files = {'file': (file.name, f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
                r = requests.post(f"{BASE_URL}/sap/upload-excel", files=files)
                if r.status_code == 200:
                    print(f"✓ {file.name} uploaded successfully")
                else:
                    print(f"✗ Upload failed: {r.json()}")
    else:
        print("No data/ directory found - skipping upload test")

def test_queries():
    print_section("5. Test Queries")
    
    queries = [
        "How many sales documents are there?",
        "What is the total net value across all documents?",
        "Show me all sales documents",
        "List all items for sales document 1",
        "What materials are in the system?",
    ]
    
    results = []
    
    for i, question in enumerate(queries, 1):
        print(f"\n{i}. Query: {question}")
        
        r = requests.post(
            f"{BASE_URL}/chat/query",
            json={"question": question}
        )
        
        if r.status_code == 200:
            data = r.json()
            print(f"   SQL: {data.get('sql', 'N/A')}")
            print(f"   Answer: {data.get('answer', 'N/A')}")
            print(f"   Rows: {data.get('row_count', 0)}")
            results.append({
                'question': question,
                'success': True,
                'sql': data.get('sql'),
                'row_count': data.get('row_count', 0)
            })
        else:
            print(f"   Error: {r.json()}")
            results.append({
                'question': question,
                'success': False,
                'error': r.json()
            })
    
    return results

def generate_report(results):
    print_section("6. Test Summary")
    
    total = len(results)
    success = sum(1 for r in results if r['success'])
    fail = total - success
    
    print(f"\nTotal Queries: {total}")
    print(f"Successful: {success} ({success/total*100:.1f}%)")
    print(f"Failed: {fail}")
    
    if fail > 0:
        print("\nFailed Queries:")
        for r in results:
            if not r['success']:
                print(f"  - {r['question']}")
                print(f"    Error: {r.get('error')}")

def main():
    print("""
╔══════════════════════════════════════════════════════════╗
║         SAP AI Assistant - Test Suite                   ║
║         Testing all endpoints and functionality          ║
╚══════════════════════════════════════════════════════════╝
""")
    
    try:
        # Run tests
        test_health()
        test_status()
        schema = test_schema()
        
        if not schema['tables']:
            print("\n⚠️  No tables loaded. Attempting to upload...")
            test_upload_excel()
            schema = test_schema()
        
        if schema['tables']:
            results = test_queries()
            generate_report(results)
        else:
            print("\n❌ No tables available for testing. Please:")
            print("   1. Place Excel files in data/ directory")
            print("   2. Restart the application")
            print("   3. Or use /sap/upload-excel endpoint")
        
        print("\n✅ Test suite completed!")
        
    except requests.exceptions.ConnectionError:
        print("\n❌ Cannot connect to server.")
        print("   Make sure the app is running: uvicorn app.main:app --reload")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise

if __name__ == "__main__":
    main()
