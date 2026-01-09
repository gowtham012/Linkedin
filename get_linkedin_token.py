#!/usr/bin/env python3
"""
LinkedIn OAuth Token Generator
Run this script to get your LinkedIn access token.
"""

import os
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import requests
from dotenv import load_dotenv

load_dotenv()

# LinkedIn OAuth endpoints
AUTHORIZATION_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"

# Your app credentials
CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID", "86srb71f7z4iiz")
CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")

# Redirect URI - must match what's configured in LinkedIn Developer Portal
PORT = 8585
REDIRECT_URI = f"http://localhost:{PORT}/callback"

# Scopes needed for posting
SCOPES = "openid profile w_member_social"


class OAuthHandler(BaseHTTPRequestHandler):
    """Handle the OAuth callback."""

    def do_GET(self):
        """Handle GET request from LinkedIn callback."""
        parsed = urlparse(self.path)

        if parsed.path == "/callback":
            query_params = parse_qs(parsed.query)

            if "code" in query_params:
                auth_code = query_params["code"][0]
                self.server.auth_code = auth_code

                # Send success response
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"""
                    <html>
                    <body style="font-family: Arial; text-align: center; padding-top: 50px;">
                        <h1>Authorization Successful!</h1>
                        <p>You can close this window and return to the terminal.</p>
                    </body>
                    </html>
                """)
            else:
                error = query_params.get("error", ["Unknown error"])[0]
                self.send_response(400)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(f"<h1>Error: {error}</h1>".encode())
                self.server.auth_code = None
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress server logs."""
        pass


def get_authorization_url():
    """Generate the LinkedIn authorization URL."""
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": "random_state_string"  # In production, use a random value
    }

    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{AUTHORIZATION_URL}?{query_string}"


def exchange_code_for_token(auth_code: str) -> dict:
    """Exchange authorization code for access token."""
    data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }

    print(f"\nDEBUG - Sending to LinkedIn:")
    print(f"  client_id: {CLIENT_ID}")
    print(f"  client_secret: {CLIENT_SECRET[:10]}...{CLIENT_SECRET[-5:]}")
    print(f"  redirect_uri: {REDIRECT_URI}")
    print(f"  code: {auth_code[:20]}...")

    response = requests.post(TOKEN_URL, data=data)
    print(f"  Response status: {response.status_code}")
    return response.json()


def main():
    print("\n" + "=" * 60)
    print("  LINKEDIN ACCESS TOKEN GENERATOR")
    print("=" * 60)

    if not CLIENT_SECRET:
        print("\nERROR: LINKEDIN_CLIENT_SECRET not found in .env file")
        return

    print(f"\nClient ID: {CLIENT_ID}")
    print(f"Redirect URI: {REDIRECT_URI}")
    print(f"Scopes: {SCOPES}")

    print("\n" + "-" * 60)
    print("IMPORTANT: Make sure your LinkedIn App has this redirect URI:")
    print(f"  {REDIRECT_URI}")
    print("-" * 60)

    input("\nPress Enter to open LinkedIn authorization page...")

    # Generate and open authorization URL
    auth_url = get_authorization_url()
    print(f"\nOpening browser...")
    print(f"If browser doesn't open, visit this URL manually:\n{auth_url}\n")
    webbrowser.open(auth_url)

    # Start local server to receive callback
    print("Waiting for authorization callback...")
    server = HTTPServer(("localhost", PORT), OAuthHandler)
    server.socket.setsockopt(__import__('socket').SOL_SOCKET, __import__('socket').SO_REUSEADDR, 1)
    server.auth_code = None
    server.handle_request()  # Handle single request

    if not server.auth_code:
        print("\nERROR: No authorization code received")
        return

    print(f"\nAuthorization code received!")
    print("Exchanging code for access token...")

    # Exchange code for token
    token_response = exchange_code_for_token(server.auth_code)

    if "access_token" in token_response:
        access_token = token_response["access_token"]
        expires_in = token_response.get("expires_in", "unknown")

        print("\n" + "=" * 60)
        print("  SUCCESS! Here's your access token:")
        print("=" * 60)
        print(f"\n{access_token}\n")
        print(f"Expires in: {expires_in} seconds (~{int(expires_in)//86400} days)")

        print("\n" + "-" * 60)
        print("Add this to your .env file:")
        print("-" * 60)
        print(f"\nLINKEDIN_ACCESS_TOKEN={access_token}")

        # Offer to update .env automatically
        update = input("\nUpdate .env file automatically? (y/n): ")
        if update.lower() == 'y':
            env_path = os.path.join(os.path.dirname(__file__), '.env')

            # Read existing .env
            if os.path.exists(env_path):
                with open(env_path, 'r') as f:
                    content = f.read()

                # Replace the token line
                if "LINKEDIN_ACCESS_TOKEN=" in content:
                    lines = content.split('\n')
                    new_lines = []
                    for line in lines:
                        if line.startswith("LINKEDIN_ACCESS_TOKEN="):
                            new_lines.append(f"LINKEDIN_ACCESS_TOKEN={access_token}")
                        else:
                            new_lines.append(line)
                    content = '\n'.join(new_lines)
                else:
                    content += f"\nLINKEDIN_ACCESS_TOKEN={access_token}"

                with open(env_path, 'w') as f:
                    f.write(content)

                print(f"\n.env file updated!")
            else:
                print("\n.env file not found. Please create it manually.")
    else:
        print("\nERROR: Failed to get access token")
        print(f"Response: {token_response}")


if __name__ == "__main__":
    main()
