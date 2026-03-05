import os
import sys
import argparse
import time
from androguard.core.apk import APK
from google_play_scraper import app
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables (API Key)
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Force UTF-8 encoding for Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

def extract_apk_metadata(apk_path):
    """Phase 1: Extract package name and permissions."""
    if not os.path.exists(apk_path):
        print(f"[-] Error: File '{apk_path}' not found.")
        return None, None
    try:
        print(f"[*] Extracting metadata from APK: {os.path.basename(apk_path)}...")
        a = APK(apk_path)
        return a.get_package(), a.get_permissions()
    except Exception as e:
        print(f"[-] Androguard Error: {e}")
        return None, None

def get_play_store_details(package_name):
    """Phase 2: Fetch Play Store details."""
    try:
        print(f"[*] Fetching Play Store details for: {package_name}...")
        result = app(package_name)
        return result.get('title', 'Unknown Title'), result.get('description', 'No description available.')
    except Exception:
        print(f"[!] Warning: App '{package_name}' not found on Play Store.")
        return None, None

def perform_ai_audit(permissions, description):
    """Phase 3: Stable AI Audit using Gemini 1.0 Pro."""
    if not GEMINI_API_KEY:
        return "Error: GEMINI_API_KEY not found in .env."

    genai.configure(api_key=GEMINI_API_KEY)
    
    # Quota optimization: Top 10 permissions mattum edukkurom
    limited_perms = permissions[:10]
    
    prompt = f"""
    Analyze these Android Permissions: {', '.join(limited_perms)}
    App Context: {description if description != 'N/A' else 'Off-market app, no description.'}
    
    OUTPUT FORMAT:
    Risk Score (1 to 10): [Score]
    Suspicious Permissions: [List any]
    AI Verdict: [Brief explanation]
    """

    try:
        # Using the older but more stable model for Free Tier quota
        model = genai.GenerativeModel('gemini-1.0-pro')
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        if "429" in str(e):
            return "[-] Quota Error: Google is throttling requests. Please wait 5 minutes."
        return f"[-] AI Error: {str(e)}"

def print_report(title, package_name, permissions, ai_report):
    """Print the final report."""
    print("\n" + "="*70)
    print(" " * 20 + "🛡️  ANDROID AUDITOR SECURITY REPORT  🛡️")
    print("="*70)
    print(f"{'App Title:':<18} {title if title else 'Unknown (Off-market)'}")
    print(f"{'Package Name:':<18} {package_name}")
    print(f"{'Permissions:':<18} {len(permissions)} found (Analyzed top 10)")
    print("-" * 70)
    print("\n[🤖 AI ANALYSIS]")
    print(ai_report)
    print("\n" + "="*70)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("apk", help="Path to APK")
    args = parser.parse_args()

    package_name, permissions = extract_apk_metadata(args.apk)
    if not package_name: return

    title, description = get_play_store_details(package_name)
    if not description: description = "N/A"

    ai_report = perform_ai_audit(permissions, description)
    print_report(title, package_name, permissions, ai_report)

if __name__ == "__main__":
    main()