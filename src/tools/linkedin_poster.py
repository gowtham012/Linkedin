"""
LinkedIn Poster Tool
Posts content to LinkedIn using the Share API (v2).
"""

import os
import requests
from typing import Dict, Any, Optional


LINKEDIN_API_URL = "https://api.linkedin.com/v2"


def get_user_profile(access_token: str) -> Optional[Dict[str, Any]]:
    """
    Get the authenticated user's LinkedIn profile to retrieve their URN.
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    try:
        response = requests.get(
            f"{LINKEDIN_API_URL}/userinfo",
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching LinkedIn profile: {e}")
        return None


def post_to_linkedin(
    content: str,
    access_token: str = None,
) -> Dict[str, Any]:
    """
    Post content to LinkedIn.

    Args:
        content: The text content to post
        access_token: LinkedIn OAuth access token (falls back to env var)

    Returns:
        Dict with success status and post ID or error message
    """
    access_token = access_token or os.getenv("LINKEDIN_ACCESS_TOKEN")

    if not access_token:
        return {"success": False, "error": "LINKEDIN_ACCESS_TOKEN not set"}

    # Get user profile to get the person URN
    profile = get_user_profile(access_token)
    if not profile:
        return {"success": False, "error": "Failed to fetch user profile"}

    # The 'sub' field contains the user ID
    user_id = profile.get("sub")
    if not user_id:
        return {"success": False, "error": "Could not get user ID from profile"}

    person_urn = f"urn:li:person:{user_id}"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    # Create the post payload using UGC Posts API
    payload = {
        "author": person_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {
                    "text": content
                },
                "shareMediaCategory": "NONE"
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        }
    }

    try:
        response = requests.post(
            f"{LINKEDIN_API_URL}/ugcPosts",
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code == 201:
            post_id = response.headers.get("X-RestLi-Id", "unknown")
            return {
                "success": True,
                "post_id": post_id,
                "message": "Post published successfully"
            }
        else:
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text}"
            }

    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e)}


def validate_linkedin_token(access_token: str = None) -> Dict[str, Any]:
    """
    Validate that the LinkedIn access token is still valid.
    """
    access_token = access_token or os.getenv("LINKEDIN_ACCESS_TOKEN")

    if not access_token:
        return {"valid": False, "error": "No access token provided"}

    profile = get_user_profile(access_token)

    if profile:
        return {
            "valid": True,
            "user_name": profile.get("name", "Unknown"),
            "user_email": profile.get("email", "Unknown"),
        }
    else:
        return {"valid": False, "error": "Token is invalid or expired"}


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    print("Validating LinkedIn token...")
    result = validate_linkedin_token()
    print(f"Token validation: {result}")

    if result.get("valid"):
        print(f"Authenticated as: {result.get('user_name')}")

        # Test post (commented out to prevent accidental posting)
        # test_content = "Testing LinkedIn API integration! 🚀 #test"
        # result = post_to_linkedin(test_content)
        # print(f"Post result: {result}")
