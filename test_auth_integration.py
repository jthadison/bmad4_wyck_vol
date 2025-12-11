"""
Integration Test Script for Authentication System

Tests the complete authentication flow:
1. User registration
2. Login (get tokens)
3. Access protected endpoint
4. Token refresh
"""

import asyncio
import json
from uuid import uuid4
import httpx

BASE_URL = "http://localhost:8000"

# Test user credentials
TEST_USER = {
    "username": f"test_user_{uuid4().hex[:8]}",
    "email": f"test_{uuid4().hex[:8]}@example.com",
    "password": "SecureTestPassword123!"
}

async def test_registration():
    """Test user registration"""
    print("\n" + "="*60)
    print("TEST 1: User Registration")
    print("="*60)

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/auth/register",
            json=TEST_USER
        )

        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")

        if response.status_code == 201:
            print("✅ Registration successful")
            return True
        else:
            print("❌ Registration failed")
            return False


async def test_login():
    """Test login and get tokens"""
    print("\n" + "="*60)
    print("TEST 2: Login")
    print("="*60)

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/auth/login",
            json={
                "username": TEST_USER["username"],
                "password": TEST_USER["password"]
            }
        )

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print("✅ Login successful")
            print(f"Access Token: {data['access_token'][:50]}...")
            print(f"Refresh Token: {data['refresh_token'][:50]}...")
            print(f"Expires In: {data['expires_in']} seconds")
            return data
        else:
            print(f"❌ Login failed: {response.text}")
            return None


async def test_protected_endpoint(access_token: str):
    """Test accessing protected endpoint"""
    print("\n" + "="*60)
    print("TEST 3: Access Protected Endpoint (User Settings)")
    print("="*60)

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/user/settings",
            headers={"Authorization": f"Bearer {access_token}"}
        )

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            print("✅ Successfully accessed protected endpoint")
            data = response.json()
            print(f"Settings Preview: user_id={data.get('user_id')}")
            return True
        else:
            print(f"❌ Failed to access protected endpoint: {response.text}")
            return False


async def test_token_refresh(refresh_token: str):
    """Test token refresh"""
    print("\n" + "="*60)
    print("TEST 4: Token Refresh")
    print("="*60)

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/auth/refresh",
            json={"refresh_token": refresh_token}
        )

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print("✅ Token refresh successful")
            print(f"New Access Token: {data['access_token'][:50]}...")
            print(f"Expires In: {data['expires_in']} seconds")
            return data['access_token']
        else:
            print(f"❌ Token refresh failed: {response.text}")
            return None


async def test_invalid_token():
    """Test protected endpoint with invalid token"""
    print("\n" + "="*60)
    print("TEST 5: Invalid Token (Should Fail)")
    print("="*60)

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/user/settings",
            headers={"Authorization": "Bearer invalid_token_here"}
        )

        print(f"Status Code: {response.status_code}")

        if response.status_code == 401:
            print("✅ Correctly rejected invalid token")
            return True
        else:
            print(f"❌ Unexpected response: {response.text}")
            return False


async def test_password_change(access_token: str):
    """Test password change"""
    print("\n" + "="*60)
    print("TEST 6: Password Change")
    print("="*60)

    new_password = "NewSecurePassword456!"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/user/change-password",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "current_password": TEST_USER["password"],
                "new_password": new_password,
                "confirm_password": new_password
            }
        )

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            print("✅ Password changed successfully")
            # Update for future tests
            TEST_USER["password"] = new_password
            return True
        else:
            print(f"❌ Password change failed: {response.text}")
            return False


async def main():
    """Run all integration tests"""
    print("\n" + "="*60)
    print("AUTHENTICATION SYSTEM INTEGRATION TESTS")
    print("="*60)
    print(f"Base URL: {BASE_URL}")
    print(f"Test User: {TEST_USER['username']}")
    print(f"Test Email: {TEST_USER['email']}")

    results = {
        "registration": False,
        "login": False,
        "protected_endpoint": False,
        "token_refresh": False,
        "invalid_token": False,
        "password_change": False
    }

    try:
        # Test 1: Registration
        results["registration"] = await test_registration()

        if not results["registration"]:
            print("\n❌ Registration failed. Cannot continue with other tests.")
            return

        # Test 2: Login
        tokens = await test_login()
        if tokens:
            results["login"] = True
            access_token = tokens["access_token"]
            refresh_token = tokens["refresh_token"]
        else:
            print("\n❌ Login failed. Cannot continue with other tests.")
            return

        # Test 3: Protected Endpoint
        results["protected_endpoint"] = await test_protected_endpoint(access_token)

        # Test 4: Token Refresh
        new_access_token = await test_token_refresh(refresh_token)
        if new_access_token:
            results["token_refresh"] = True
            access_token = new_access_token  # Use new token for remaining tests

        # Test 5: Invalid Token
        results["invalid_token"] = await test_invalid_token()

        # Test 6: Password Change
        results["password_change"] = await test_password_change(access_token)

    except httpx.ConnectError:
        print("\n❌ ERROR: Cannot connect to API server")
        print("Make sure the FastAPI server is running on http://localhost:8000")
        print("Start with: cd backend && poetry run uvicorn src.api.main:app --reload")
        return
    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return

    # Print Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    total_tests = len(results)
    passed_tests = sum(1 for v in results.values() if v)

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name.replace('_', ' ').title()}")

    print("\n" + "="*60)
    print(f"Results: {passed_tests}/{total_tests} tests passed")
    print("="*60)

    if passed_tests == total_tests:
        print("\n🎉 All integration tests passed!")
    else:
        print(f"\n⚠️  {total_tests - passed_tests} test(s) failed")


if __name__ == "__main__":
    asyncio.run(main())
