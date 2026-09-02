import requests

# 1. Enter your Upstox Developer Credentials
API_KEY = "YOUR_UPSTOX_API_KEY"
API_SECRET = "YOUR_UPSTOX_API_SECRET"
REDIRECT_URI = "http://localhost:8080/"  # Must exactly match your Upstox dashboard

def step_1_get_login_url():
    """Generates the URL you need to paste into your browser to log in."""
    url = (
        f"https://upstox.com"
        f"?client_id={API_KEY}&redirect_uri={REDIRECT_URI}&response_type=code"
    )
    print("\n--- STEP 1: COPY & PASTE THIS URL INTO YOUR BROWSER ---")
    print(url)
    print("-------------------------------------------------------\n")

def step_2_exchange_code_for_token(auth_code):
    """Exchanges the browser code for your daily active Access Token."""
    url = "https://upstox.com"
    
    headers = {
        "accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    data = {
        "code": auth_code,
        "client_id": API_KEY,
        "client_secret": API_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code"
    }
    
    response = requests.post(url, headers=headers, data=data)
    res_json = response.json()
    
    if "access_token" in res_json:
        print("\n--- STEP 3: SUCCESS! YOUR ACCESS TOKEN IS BELOW ---")
        print(res_json["access_token"])
        print("---------------------------------------------------\n")
        print("Copy this token and update your GitHub Repository Secret: UPSTOX_ACCESS_TOKEN")
    else:
        print("\n❌ Error generating token:", res_json)

if __name__ == "__main__":
    # Run Step 1 to get your login link
    step_1_get_login_url()
    
    # Wait for the user to log in and provide the code from the redirected URL
    print("Log in via your mobile/OTP. After logging in, your browser will redirect to a broken page.")
    print("Look at the address bar of that page. Example: http://localhost:8080/?code=XXXXXX")
    user_code = input("Enter the 'code' value from the URL here: ").strip()
    
    if user_code:
        step_2_exchange_code_for_token(user_code)
    else:
        print("No code provided. Exiting.")
