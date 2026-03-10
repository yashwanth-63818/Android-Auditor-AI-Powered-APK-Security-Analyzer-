import os
import sys
import argparse
import re
import datetime
import google.generativeai as genai

# Robust dependency handling
try:
    from androguard.core.apk import APK
    from androguard.core.dex import DEX
except ImportError:
    print("[-] Error: Androguard not found. Run 'pip install androguard'")
    sys.exit(1)

try:
    from fpdf import FPDF
except ImportError:
    try:
        from fpdf2 import FPDF
    except ImportError:
        # Define a mock FPDF class to prevent inheritance errors
        class FPDF:
            def __getattr__(self, name):
                return lambda *args, **kwargs: None

from google_play_scraper import app
from dotenv import load_dotenv

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

# --- CONFIGURATION & HIGH-ACCURACY REGEX ---

SECRET_REGEX = {
    "Google API Key": r"AIza[0-9A-Za-z\-_]{35}",
    "Firebase URL": r"https?://[a-z0-9.-]+\.firebaseio\.com",
    "AWS Access Key": r"AKIA[0-9A-Z]{16}",
    "AWS S3 Bucket": r"[a-z0-9.-]+\.s3\.amazonaws\.com",
    "Private IP/URL": r"\b(10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2[0-9]|3[0-1])\.\d{1,3}\.\d{1,3})\b",
    "Sensitive Keyword": r"(?i)password|secret_key|auth_token"
}

# --- PDF REPORT CLASS ---

class ProfessionalReport(FPDF):
    def header(self):
        if not hasattr(self, 'set_fill_color'): return
        self.set_fill_color(30, 41, 59) # Pro Midnight Slate
        self.rect(0, 0, 210, 40, 'F')
        self.set_text_color(255, 255, 255)
        self.set_font("Arial", 'B', 20)
        self.cell(0, 20, "VAPT AUDIT REPORT: ANDROID", 0, 1, 'C')
        self.set_font("Arial", '', 10)
        self.cell(0, -5, f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}", 0, 1, 'C')
        self.ln(25)

    def footer(self):
        if not hasattr(self, 'set_y'): return
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, f'Page {self.page_no()} | Confidential MAST Audit', 0, 0, 'C')

# --- CORE FUNCTIONS ---

def extract_manifest_risks(apk_obj):
    """Checks for core manifest vulnerabilities."""
    try:
        manifest = apk_obj.get_android_manifest_xml()
        app_tag = manifest.find(".//application")
        ns = "{http://schemas.android.com/apk/res/android}"
        
        allow_backup = app_tag.get(f"{ns}allowBackup", "true")
        debuggable = app_tag.get(f"{ns}debuggable", "false")
        
        exported_count = 0
        for tag in ["activity", "service", "receiver", "provider"]:
            for item in manifest.findall(f".//{tag}"):
                exported = item.get(f"{ns}exported")
                if exported == "true" or (exported is None and item.find("intent-filter") is not None):
                    exported_count += 1
                    
        return {"allowBackup": allow_backup, "debuggable": debuggable, "exported_count": exported_count}
    except:
        return {"allowBackup": "unknown", "debuggable": "unknown", "exported_count": 0}

def hunt_secrets(apk_obj):
    """Scans DEX strings for high-accuracy secret patterns."""
    found = []
    try:
        for dex in apk_obj.get_all_dex():
            d = DEX(dex)
            for s in d.get_strings():
                for name, pattern in SECRET_REGEX.items():
                    if re.search(pattern, s):
                        if len(s) < 200: # Filter out binary noise
                            entry = {"type": name, "match": s.strip()}
                            if entry not in found: found.append(entry)
    except: pass
    return found

def get_ai_audit(package, permissions, description, manifest_risks, secrets):
    """Performs deep AI analysis with stable model fallback."""
    if not GEMINI_API_KEY:
        return "ERROR: Missing GEMINI_API_KEY in .env"

    genai.configure(api_key=GEMINI_API_KEY)
    
    secrets_str = "\n".join([f"- {s['type']}: {s['match']}" for s in secrets]) or "None"
    
    prompt = f"""
    ROLE: Senior Mobile Security Researcher.
    TASK: Professional MAST Analysis for Android APK.
    
    INPUT:
    Package: {package}
    Permissions: {', '.join(permissions)}
    Manifest: Backup={manifest_risks['allowBackup']}, Debug={manifest_risks['debuggable']}, Exported={manifest_risks['exported_count']}
    Secrets Detected: {secrets_str}
    App Description: {description[:1000]}

    OUTPUT FORMAT:
    SUMMARY_START
    RISK SCORE: [0-10]
    VERDICT: [Safe, Suspicious, or Malicious]
    TOP FINDINGS: [Brief list of top 3 issues]
    SUMMARY_END

    VULNERABILITIES_START
    - [Issue Name] | [OWASP Category] | Remediation: [Steps]
    VULNERABILITIES_END
    """

    # Model Fallback List (Gemini 2.0 & 1.5 Support)
    models_to_try = ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-pro']
    
    for model_name in models_to_try:
        try:
            print(f"[*] Attempting AI Audit with {model_name}...")
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            if response and response.text:
                return response.text.strip()
        except Exception as e:
            continue
            
    return "AI_ERROR: Audit Timeout - Check Connection / API Status"

def get_mock_audit(package, permissions, manifest_risks, secrets):
    """Provides a static security report if AI is unavailable."""
    risk_score = 5
    if manifest_risks['debuggable'] == "true" or secrets:
        risk_score = 8
        
    return f"""
    SUMMARY_START
    RISK SCORE: {risk_score}
    VERDICT: Suspicious (Static Analysis)
    TOP FINDINGS: Hardcoded secrets detection, Manifest hardening issues, Permission over-reach.
    SUMMARY_END

    VULNERABILITIES_START
    - Manifest Hardening | M1: Improper Platform Usage | Remediation: Disable 'debuggable' and 'allowBackup' in AndroidManifest.xml unless strictly necessary.
    - Component Exposure | M1: Improper Platform Usage | Remediation: Review exported components ({manifest_risks['exported_count']} found) and restrict with permissions.
    - Security Secrets | M2: Insecure Data Storage | Remediation: Remove hardcoded secrets ({len(secrets)} found) and use Android Keystore or secure backend.
    - Permissions Check | M1: Improper Platform Usage | Remediation: Review {len(permissions)} permissions for least-privilege compliance.
    VULNERABILITIES_END
    """

def parse_summary(ai_response):
    """Robust parser for terminal executive summary."""
    if "AI_ERROR" in ai_response:
        return {"score": "N/A", "findings": "Connection Failed", "verdict": "Error"}

    # Case-insensitive Regex searching for tags
    score_match = re.search(r"RISK SCORE:\s*(\d+)", ai_response, re.IGNORECASE)
    verdict_match = re.search(r"VERDICT:\s*([^\n\r]*)", ai_response, re.IGNORECASE)
    findings_match = re.search(r"TOP FINDINGS:\s*([^\n\r]*)", ai_response, re.IGNORECASE)

    return {
        "score": score_match.group(1).strip() if score_match else "N/A",
        "verdict": verdict_match.group(1).strip() if verdict_match else "Unknown",
        "findings": findings_match.group(1).strip() if findings_match else "No findings parsed."
    }

def generate_pdf(pkg_name, app_title, ai_response):
    """Generates the structured PDF report if AI response is valid."""
    # Check if FPDF is a real class (has methods)
    if not hasattr(FPDF, 'add_page'):
        print("[!] FPDF not installed. Skipping PDF.")
        return

    pdf = ProfessionalReport()
    try:
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, f"Analysis for: {app_title if app_title != 'Unknown' else pkg_name}", 0, 1)
        pdf.ln(5)

        clean_report = ai_response.encode('latin-1', 'ignore').decode('latin-1')

        # Section 1: Executive Summary
        pdf.set_font("Arial", 'B', 12)
        pdf.set_fill_color(241, 245, 249)
        pdf.cell(0, 10, " 1. Security Analysis Overview", 0, 1, 'L', 1)
        pdf.set_font("Arial", '', 10); pdf.ln(3)

        summary_match = re.search(r"SUMMARY_START(.*?)SUMMARY_END", clean_report, re.DOTALL | re.IGNORECASE)
        if summary_match:
            pdf.multi_cell(0, 6, summary_match.group(1).strip())
        else:
            pdf.multi_cell(0, 6, clean_report.split("VULNERABILITIES_START")[0][:1000])
        pdf.ln(5)

        # Section 2: Detailed Vulnerabilities
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, " 2. Detailed Vulnerabilities & Remediation", 0, 1, 'L', 1)
        pdf.ln(3); pdf.set_font("Arial", '', 10)
        
        vuln_match = re.search(r"VULNERABILITIES_START(.*?)VULNERABILITIES_END", clean_report, re.DOTALL | re.IGNORECASE)
        if vuln_match:
            pdf.multi_cell(0, 7, vuln_match.group(1).strip())
        else:
            pdf.multi_cell(0, 7, clean_report)

        filename = f"MAST_Audit_{pkg_name}.pdf"
        pdf.output(filename)
        print(f"\n[+] Professional PDF generated: {filename}")
    except Exception as e:
        print(f"[-] PDF error: {e}")

def main():
    parser = argparse.ArgumentParser(description="Professional Android Security Auditor")
    parser.add_argument("apk", nargs="?", default="test.apk", help="Path to APK")
    args = parser.parse_args()

    # Environment reminder
    print("[!] Reminder: Run 'pip install -U google-generativeai fpdf' for optimal results.\n")

    print("\n" + "="*60 + "\n      🛡️  ANDROID AUDITOR PROFESSIONAL MAST SUITE  🛡️\n" + "="*60)

    if not os.path.exists(args.apk):
        print(f"[-] Error: {args.apk} not found."); return

    print(f"[*] Analyzing Binary: {os.path.basename(args.apk)}")
    try:
        a = APK(args.apk)
        pkg = a.get_package()
    except Exception as e:
        print(f"[-] Error parsing APK: {e}"); return
    
    m_risks = extract_manifest_risks(a)
    secrets = hunt_secrets(a)
    
    print(f"[*] Fetching Play Store data for {pkg}...")
    try:
        app_data = app(pkg, lang='en', country='us')
        title, desc = app_data.get('title', 'Unknown'), app_data.get('description', 'N/A')
    except:
        title, desc = "Unknown", "Offline analysis: No description available."

    print("[*] Running AI Security Correlation...")
    ai_report = get_ai_audit(pkg, a.get_permissions(), desc, m_risks, secrets)
    
    is_mock = False
    if "AI_ERROR" in ai_report:
        print("\n[!] AI Audit Failed (API issue).")
        mock_choice = input("[?] Would you like to use the Static Mock Report backup? (y/n): ").lower()
        if mock_choice == 'y':
            ai_report = get_mock_audit(pkg, a.get_permissions(), m_risks, secrets)
            is_mock = True
        else:
            print("\n[-] Scan halted. Check connection or API key."); return

    summary = parse_summary(ai_report)
    print("\n" + "-"*30 + " EXECUTIVE SUMMARY " + (" (MOCK)" if is_mock else "") + " " + "-"*30)
    print(f"[+] App Name:  {title}")
    print(f"[!] Risk Score: {summary['score']}/10")
    print(f"[!] Verdict:    {summary['verdict']}")
    print(f"[!] Findings:   {summary['findings']}")
    print("-" * 79)

    choice = input("\n[?] Would you like to generate a detailed PDF Audit Report? (y/n): ").lower()
    if choice == 'y':
        generate_pdf(pkg, title, ai_report)
    else:
        print("\n[+] Scan Complete. Performance optimized.")

    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    main()