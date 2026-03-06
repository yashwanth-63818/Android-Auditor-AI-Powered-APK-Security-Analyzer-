import os
import sys
import argparse
import time
import google.generativeai as genai
from androguard.core.apk import APK
from google_play_scraper import app
from dotenv import load_dotenv
from fpdf import FPDF # PDF library

# Initialize Environment
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Force UTF-8 encoding for Windows terminals
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        import codecs
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

def extract_apk_metadata(apk_path):
    """Phase 1: Binary Analysis - Extracts Package ID and Permissions."""
    if not os.path.exists(apk_path):
        print(f"[-] Error: APK file '{apk_path}' not found.")
        return None, None
    try:
        print(f"[*] Processing APK: {os.path.basename(apk_path)}...")
        a = APK(apk_path)
        return a.get_package(), a.get_permissions()
    except Exception as e:
        print(f"[-] Meta Extraction failed: {e}")
        return None, None

def get_play_store_details(package_name):
    """Phase 2: App Context Scraper - Gets Title and Description."""
    try:
        print(f"[*] Fetching Play Store data for: {package_name}...")
        result = app(package_name, lang='en', country='us')
        return result.get('title', 'Unknown'), result.get('description', 'N/A')
    except:
        return None, "No description available (Likely off-market app)."

def perform_ai_audit(permissions, description):
    """Phase 3: AI Security Review."""
    if not GEMINI_API_KEY:
        return "[-] Error: API Key missing in .env (GEMINI_API_KEY)."

    genai.configure(api_key=GEMINI_API_KEY)

    models_to_try = [
        'gemini-1.5-flash', 
        'gemini-1.5-flash-8b', 
        'gemini-1.0-pro', 
        'gemini-2.0-flash', 
        'gemini-flash-latest'
    ]

    prompt_text = f"""
    ROLE: Senior Mobile Security Auditor.
    CONTEXT:
    App Description: {description[:1200]}
    Permissions: {', '.join(permissions)}
    
    GOAL: Evaluate if the app's permissions are excessive or suspicious given its description. 
    
    OUTPUT FORMAT:
    RISK SCORE: [0-10]
    VERDICT: [Safe, Suspicious, or Malicious]
    ANALYSIS: [Explain suspicious permissions]
    """

    for model_name in models_to_try:
        try:
            print(f"[*] Auditing with AI ({model_name})...")
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt_text)
            if response and response.text:
                return response.text.strip()
        except Exception as e:
            continue

    return "[-] AI Audit Failed: No responding models found."

def save_report_as_pdf(title, pkg, perms_count, ai_report):
    """Saves the audit results into a PDF file."""
    try:
        pdf = FPDF()
        pdf.add_page()
        
        # Title
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, txt="ANDROID APK SECURITY AUDIT REPORT", ln=True, align='C')
        pdf.ln(10)
        
        # App Info
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, txt=f"App Title: {title if title else 'Unknown'}", ln=True)
        pdf.cell(0, 10, txt=f"Package ID: {pkg}", ln=True)
        pdf.cell(0, 10, txt=f"Permissions Scanned: {perms_count}", ln=True)
        pdf.ln(5)
        pdf.cell(0, 0, "", "T", 1) # Horizontal Line
        pdf.ln(5)
        
        # AI Report Content
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, txt="AI SECURITY ANALYSIS RESULTS:", ln=True)
        pdf.ln(2)
        
        pdf.set_font("Arial", size=11)
        # Cleaning text for Latin-1 (PDF limitation)
        clean_text = ai_report.encode('latin-1', 'ignore').decode('latin-1')
        pdf.multi_cell(0, 7, txt=clean_text)
        
        filename = f"Audit_Report_{pkg}.pdf"
        pdf.output(filename)
        print(f"[+] PDF Report Generated: {filename}")
    except Exception as e:
        print(f"[-] PDF Generation Error: {e}")

def display_report(title, pkg, perms, ai_report):
    """Final output formatting."""
    print("\n" + "═"*75)
    print(" " * 20 + "🛡️  ANDROID APK SECURITY AUDIT REPORT  🛡️")
    print("═"*75)
    print(f"APP:  {title if title else 'Offline / Unknown'}")
    print(f"ID:   {pkg}")
    print(f"SCAN: {len(perms)} permissions checked")
    print("-" * 75)
    print("\n[🤖 2026 AI SECURITY RESULTS]")
    print(ai_report)
    print("\n" + "═"*75 + "\n")

def main():
    parser = argparse.ArgumentParser(description="AI Android Security Auditor")
    parser.add_argument("apk", nargs="?", default="test.apk", help="Path to APK file")
    args = parser.parse_args()

    # Step 1: Extraction
    pkg, perms = extract_apk_metadata(args.apk)
    if not pkg: 
        print("[-] Could not proceed without APK metadata.")
        return

    # Step 2: Enrichment
    title, desc = get_play_store_details(pkg)

    # Step 3: Audit
    report = perform_ai_audit(perms, desc)

    # Step 4: Show Results & Save PDF
    display_report(title, pkg, perms, report)
    save_report_as_pdf(title, pkg, len(perms), report)

if __name__ == "__main__":
    main()