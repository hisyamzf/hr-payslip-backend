import requests
import time
import sys

BASE_URL = "http://localhost:8000"

def test_health():
    print("\n=== Test 1: Health Check ===")
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.json()}")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_root():
    print("\n=== Test 2: Root Endpoint ===")
    try:
        resp = requests.get(f"{BASE_URL}/", timeout=5)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.json()}")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_docs():
    print("\n=== Test 3: OpenAPI Docs ===")
    try:
        resp = requests.get(f"{BASE_URL}/openapi.json", timeout=5)
        print(f"Status: {resp.status_code}")
        data = resp.json()
        paths = list(data.get('paths', {}).keys())
        print(f"Total endpoints: {len(paths)}")
        print(f"Sample paths: {paths[:10]}")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

def main():
    print("Testing HR Payslip Backend API...")
    print("=" * 50)
    
    if not test_health():
        print("\n❌ Backend not running! Start with: python run.py")
        sys.exit(1)
    
    test_root()
    test_docs()
    
    print("\n" + "=" * 50)
    print("✅ All basic tests passed!")
    print("\nNext: Test frontend at http://localhost:5173/")

if __name__ == "__main__":
    main()