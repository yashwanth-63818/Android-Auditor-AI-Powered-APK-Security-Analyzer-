import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def test_config():
    print(f"[*] Testing with Key: {GEMINI_API_KEY[:8]}...")
    try:
        print("[*] Trying version='v1'...")
        genai.configure(api_key=GEMINI_API_KEY, transport='rest', version='v1')
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content("ping")
        print(f"[+] Success with version='v1'! Response: {response.text}")
        return True
    except Exception as e:
        print(f"[-] Failed with version='v1': {e}")
        try:
            print("[*] Trying no version arg...")
            genai.configure(api_key=GEMINI_API_KEY, transport='rest')
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content("ping")
            print(f"[+] Success with no version arg! Response: {response.text}")
            return True
        except Exception as e2:
            print(f"[-] Failed with no version arg: {e2}")
            return False

if __name__ == "__main__":
    test_config()
