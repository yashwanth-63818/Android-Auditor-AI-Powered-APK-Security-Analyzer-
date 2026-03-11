import warnings
warnings.filterwarnings("ignore")
import os
import sys
import argparse
import re
import datetime
import subprocess
import socket
import google.generativeai as genai
import requests
import json
import time
from colorama import Fore, Style, init
init(autoreset=True)

# Terminal Color Palette (Professional Hacker Theme)
B = Style.BRIGHT
C = Fore.CYAN + Style.BRIGHT
G = Fore.GREEN + Style.BRIGHT
R = Fore.RED + Style.BRIGHT
Y = Fore.YELLOW + Style.BRIGHT
M = Fore.MAGENTA + Style.BRIGHT
W = Fore.WHITE + Style.BRIGHT
D = Fore.BLACK + Style.BRIGHT # Dim Grey
RESET = Style.RESET_ALL

def clear_screen():
    """Clears the terminal screen for a clean UX."""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_banner():
    print(f"\n{B}{M}" + "="*65)
    print(f"      🛡️   M O B I L E   A U D I T O R   P R O   v1.5   🛡️")
    print("="*65 + f"{RESET}\n")

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

APP_CATEGORY_RULES = {
    "Calculator": {
        "forbidden": ["android.permission.RECORD_AUDIO", "android.permission.CAMERA", "android.permission.READ_SMS", "android.permission.ACCESS_FINE_LOCATION"],
        "keywords": ["calculator", "math", "calculation"]
    },
    "Flashlight": {
        "forbidden": ["android.permission.READ_CONTACTS", "android.permission.SEND_SMS", "android.permission.READ_SMS", "android.permission.RECORD_AUDIO"],
        "keywords": ["flashlight", "torch", "light"]
    },
    "Game": {
        "forbidden": ["android.permission.READ_CALL_LOG", "android.permission.SEND_SMS", "android.permission.READ_SMS", "android.permission.PROCESS_OUTGOING_CALLS"],
        "keywords": ["game", "play", "puzzle", "arcade", "racer", "action"]
    },
    "Wallpaper": {
        "forbidden": ["android.permission.RECORD_AUDIO", "android.permission.READ_SMS", "android.permission.SEND_SMS", "android.permission.READ_CONTACTS"],
        "keywords": ["wallpaper", "background", "theme"]
    },
    "Tool/Utility": {
        "forbidden": ["android.permission.SEND_SMS", "android.permission.READ_CALL_LOG"],
        "keywords": ["tool", "utility", "compress", "converter"]
    }
}

def is_google_reachable():
    """Simple check to see if Google is reachable (8.8.8.8) to verify connectivity."""
    try:
        socket.setdefaulttimeout(3)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return True
    except (socket.timeout, socket.error):
        return False

def run_adb(command):
    """Helper to run ADB commands and return output."""
    try:
        result = subprocess.run(["adb"] + command.split(), capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except Exception as e:
        return None

def get_adb_packages():
    """Lists 3rd party packages from connected device with error handling."""
    while True:
        print(f"{C}[*] Detecting connected devices...{W}")
        devices = run_adb("devices")
        
        # Check if any device is listed (header is line 1, device should be line 2)
        device_found = False
        if devices:
            lines = [l for l in devices.split("\n") if l.strip()]
            if len(lines) > 1: # More than just "List of devices attached"
                device_found = True
        
        if not device_found:
            print(f"\n{B}{R}[!] ERROR: NO DEVICE CONNECTED VIA USB.{W}")
            print(f"{Y} [R] Retry ADB Scan{W}")
            print(f"{Y} [E] Exit to Main Menu{W}")
            sub_choice = input(f"\n{Y}[?] Choice: {W}").strip().upper()
            if sub_choice == 'R':
                continue
            return "EXIT"
        
        print(f"{C}[*] Fetching 3rd-party packages...{W}")
        pkgs = run_adb("shell pm list packages -3")
        if not pkgs: 
            print(f"{R}[-] No 3rd-party packages found.{W}")
            return None
        
        list_pkgs = [p.replace("package:", "") for p in pkgs.split("\n") if p.strip()]
        return list_pkgs

def pull_apk_from_adb(package_name):
    """Gets the path of a package and pulls the APK."""
    print(f"{C}[*] Locating remote path for {package_name}...{W}")
    path_info = run_adb(f"shell pm path {package_name}")
    if not path_info: 
        print(f"{R}[-] Failed to locate APK on device.{W}")
        return None
    
    apk_remote_path = path_info.split(":")[1].strip()
    local_filename = f"{package_name}.apk"
    print(f"{C}[*] Pulling Binary: {local_filename}...{W}")
    
    # Use subprocess directly for better control
    pull_res = subprocess.run(["adb", "pull", apk_remote_path, local_filename], capture_output=True)
    if os.path.exists(local_filename):
        print(f"{G}[+] APK Pulled Successfully.{W}")
        return local_filename
    return None

def diagnostic_connection_test():
    """Diagnostic check for Gemini API status and Key validity."""
    if not GEMINI_API_KEY:
        print("\n[!] CRITICAL: Missing GEMINI_API_KEY in .env file.")
        return False

    print("[*] Performing Diagnostic Connection Test...")
    
    # 1. Check Google reachability
    if not is_google_reachable():
        print("[!] Diagnostic: 8.8.8.8 Unreachable. Check your network/proxy.")
        return "NETWORK_ERROR"

    print(f"{C}[*] Connecting to Stable Gemini Engine....{W}")
    
    # 2. Check API Key validity via small request
    try:
        # Force v1 Stable endpoint via specified initialization
        try:
            genai.configure(api_key=GEMINI_API_KEY, transport='rest', api_version='v1')
        except TypeError:
            genai.configure(api_key=GEMINI_API_KEY, transport='rest')
            
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Test request
        response = model.generate_content("ping", request_options={'timeout': 10})

        if response:
            print(f"{G}[+] Diagnostic: Gemini API is LIVE and Key is VALID.{W}")
            return True
    except Exception as e:
        err_msg = str(e).upper()
        if "404" in err_msg:
             print(f"{C}[*] Switching to Local Heuristic Engine (Offline Audit Mode){W}")
             # Test fallback anyway for diagnostics
             try:
                 url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
                 resp = requests.post(url, json={"contents": [{"parts": [{"text": "ping"}]}]}, timeout=10)
                 if resp.status_code == 200:
                     print(f"{G}[+] Diagnostic: Stable V1 Reachable via REST Fallback.{W}")
                     return True
             except: pass
             return "AI_OFFLINE"
             
        if "API_KEY_INVALID" in err_msg or "INVALID_ARGUMENT" in err_msg:
            print("\n" + "!"*60)
            print("  CRITICAL: Update your API Key in the .env file.")
            print("  The current key is either EXPIRED or INVALID.")
            print("!"*60 + "\n")
            return "KEY_ERROR"
        else:
            print(f"[!] Diagnostic: Gemini API test failed - {e}")
            return "AI_OFFLINE"
    return False

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

def get_ai_audit(package, permissions, description, manifest_risks, secrets, app_title):
    """Performs deep AI analysis with dynamic model selection and REST transport."""
    if not GEMINI_API_KEY:
        return "ERROR: Missing GEMINI_API_KEY in .env"

    try:
        # Pre-check connectivity
        if not is_google_reachable():
            return "AI_ERROR: No Internet Connection."

        # FORCE v1 Stable API Production Endpoint & Disable Beta
        # Using specified api_version='v1'
        try:
            genai.configure(api_key=GEMINI_API_KEY, transport='rest', api_version='v1')
        except TypeError:
            genai.configure(api_key=GEMINI_API_KEY, transport='rest')
            
        # Use specified model name (Stable)
        model = genai.GenerativeModel('gemini-1.5-flash')
        print(f"[*] Initializing Production Model: gemini-1.5-flash (v1 Stable)")
        
    except Exception as e:
        return f"AI_ERROR: API Configuration failed - {e}"
    
    secrets_str = "\n".join([f"- {s['type']}: {s['match']}" for s in secrets]) or "None"
    
    prompt = f"""
    ROLE: Senior Mobile Security Researcher.
    TASK: Professional MAST Analysis for Android APK.
    
    APP CONTEXT:
    App Name: {app_title}
    Package: {package}
    App Description: {description[:1000]}
    
    SECURITY DATA:
    Permissions: {', '.join(permissions)}
    Manifest: Backup={manifest_risks['allowBackup']}, Debug={manifest_risks['debuggable']}, Exported={manifest_risks['exported_count']}
    Secrets Detected: {secrets_str}

    GOAL: 
    1. Specifically analyze if the permissions align with the App Name and Description.
    2. Identify "Unwanted/Suspicious Permissions" (e.g., a simple app like a calculator or flashlight asking for SMS/Camera/Location).
    3. Map all findings to OWASP Mobile Top 10 categories (M1-M10).

    OUTPUT FORMAT:
    SUMMARY_START
    RISK SCORE: [0-10]
    VERDICT: [Safe, Suspicious, or Malicious]
    TOP FINDINGS: [Brief list of top 3 issues]
    SUMMARY_END

    TABLE_START
    [Vulnerability or Permission Name] | [Contextual Risk Analysis - Be specific about UNWANTED permissions vs app name] | [OWASP Category] | [Remediation Steps]
    ...
    TABLE_END
    """

    try:
        # Increased timeout for complex mobile security prompts
        response = model.generate_content(prompt, request_options={'timeout': 300})
        if response and response.text:
            return response.text.strip()
    except Exception as e:
        err_str = str(e)
        # Force REST fallback for 404 or any configuration issue
        if "404" in err_str or "API_VERSION" in err_str.upper():
            print("[!] API Version Issue or 404. Attempting direct HTTP POST fallback (v1 Stable)...")
            try:
                url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
                headers = {'Content-Type': 'application/json'}
                payload = {
                    "contents": [{
                        "parts": [{"text": prompt}]
                    }]
                }
                resp = requests.post(url, headers=headers, json=payload, timeout=300)
                if resp.status_code == 200:
                    data = resp.json()
                    # Extract text from the REST response structure
                    return data['candidates'][0]['content']['parts'][0]['text'].strip()
                else:
                    return f"AI_ERROR: HTTP Fallback failed with status {resp.status_code} - {resp.text}"
            except Exception as fallback_err:
                return f"AI_ERROR: HTTP Fallback failed - {fallback_err}"
        
        return f"AI_ERROR: Model generation failed - {e}"
            
    return "AI_ERROR: Audit Timeout - Check Connection / API Status"

def get_mock_audit(package, permissions, manifest_risks, secrets, app_title):
    """Provides a static security report using 'Air-Gapped Internal Logic Engine'."""
    risk_score = 4
    findings = []
    
    # Identify App Category
    detected_category = "General"
    for cat, rules in APP_CATEGORY_RULES.items():
        if any(kw in (app_title + " " + package).lower() for kw in rules['keywords']):
            detected_category = cat
            break
            
    # Check for Forbidden Permissions (M1)
    forbidden_matches = []
    if detected_category in APP_CATEGORY_RULES:
        for p in permissions:
            if any(fp in p for fp in APP_CATEGORY_RULES[detected_category]['forbidden']):
                forbidden_matches.append(p.split(".")[-1])
                risk_score += 2
                
    if manifest_risks['debuggable'] == "true": risk_score += 2
    if secrets: risk_score += 3
    risk_score = min(risk_score, 10)
    
    verdict = "Safe" if risk_score < 5 else ("Suspicious" if risk_score < 8 else "Malicious")
    
    rows = []
    if forbidden_matches:
        rows.append(f"Permission Misalignment | UNWANTED: {app_title} ({detected_category}) requests {', '.join(forbidden_matches)}. | M1: Improper Platform Usage | Review and remove redundant permissions.")
    else:
        rows.append(f"Permissions | {app_title} categorized as {detected_category}. Permissions seem standard for this type. | Info | No immediate action.")
        
    if manifest_risks['allowBackup'] == "true":
        rows.append(f"Manifest: allowBackup | Set to true. Potential data leak via adb backup. | M2: Insecure Data Storage | Set allowBackup=\"false\" in Manifest.")
    
    if manifest_risks['debuggable'] == "true":
        rows.append(f"Manifest: debuggable | Debugging is enabled. Vulnerable to reverse engineering. | M1: Improper Platform Usage | Set debuggable=\"false\" for production.")

    # Secrets mapping to M2
    for s in secrets[:5]:
        rows.append(f"Hardcoded Secret | Found {s['type']}: {s['match'][:20]}... | M2: Insecure Data Storage | Use Secrets Manager or Android Keystore.")

    table_content = "\n    ".join(rows)

    return f"""
    SUMMARY_START
    RISK SCORE: {risk_score}
    VERDICT: {verdict}
    TOP FINDINGS: {('Found ' + ', '.join(forbidden_matches)) if forbidden_matches else 'No high-risk permissions'}, Secrets={len(secrets)}, Exported={manifest_risks['exported_count']}.
    SUMMARY_END

    TABLE_START
    {table_content}
    TABLE_END
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
    """Generates the structured PDF report with a professional table."""
    if not hasattr(FPDF, 'add_page'):
        print("[!] FPDF not installed. Skipping PDF.")
        return None

    pdf = ProfessionalReport()
    try:
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, f"VAPT Report: {app_title if app_title != 'Unknown' else pkg_name}", 0, 1)
        pdf.set_font("Arial", '', 10)
        pdf.cell(0, 5, f"Package: {pkg_name}", 0, 1)
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
        pdf.ln(5)

        # Section 2: Detailed Vulnerability Table
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, " 2. Detailed Findings & Remediation Guide", 0, 1, 'L', 1)
        pdf.ln(3)

        # Table Header
        pdf.set_font("Arial", 'B', 9)
        pdf.set_fill_color(30, 41, 59)
        pdf.set_text_color(255, 255, 255)
        
        widths = [40, 60, 30, 60]
        pdf.cell(widths[0], 10, "Component / Vulnerability", 1, 0, 'C', 1)
        pdf.cell(widths[1], 10, "Contextual Risk Analysis", 1, 0, 'C', 1)
        pdf.cell(widths[2], 10, "OWASP Cat.", 1, 0, 'C', 1)
        pdf.cell(widths[3], 10, "Remediation Guide", 1, 1, 'C', 1)

        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", '', 8)

        # Parse Table Data
        table_match = re.search(r"TABLE_START(.*?)TABLE_END", clean_report, re.DOTALL | re.IGNORECASE)
        if table_match:
            rows = table_match.group(1).strip().split("\n")
            for row in rows:
                if "|" not in row: continue
                cols = [c.strip() for c in row.split("|")]
                if len(cols) < 4: continue

                is_suspicious = "UNWANTED" in cols[1].upper() or "SUSPICIOUS" in cols[1].upper()
                fill = 1 if is_suspicious else 0
                if fill: pdf.set_fill_color(255, 235, 235)

                x_start = pdf.get_x()
                y_start = pdf.get_y()
                line_height = 5
                
                if y_start > 250:
                    pdf.add_page()
                    pdf.set_font("Arial", 'B', 9)
                    pdf.set_fill_color(30, 41, 59)
                    pdf.set_text_color(255, 255, 255)
                    pdf.cell(widths[0], 10, "Component / Vulnerability", 1, 0, 'C', 1)
                    pdf.cell(widths[1], 10, "Contextual Risk Analysis", 1, 0, 'C', 1)
                    pdf.cell(widths[2], 10, "OWASP Cat.", 1, 0, 'C', 1)
                    pdf.cell(widths[3], 10, "Remediation Guide", 1, 1, 'C', 1)
                    pdf.set_text_color(0, 0, 0)
                    pdf.set_font("Arial", '', 8)
                    y_start = pdf.get_y()

                pdf.set_xy(x_start, y_start)
                pdf.multi_cell(widths[0], line_height, cols[0], 1, 'L', fill)
                h1 = pdf.get_y() - y_start
                
                pdf.set_xy(x_start + widths[0], y_start)
                if is_suspicious:
                    pdf.set_text_color(185, 28, 28)
                    pdf.set_font("Arial", 'B', 8)
                pdf.multi_cell(widths[1], line_height, cols[1], 1, 'L', fill)
                pdf.set_text_color(0, 0, 0)
                pdf.set_font("Arial", '', 8)
                h2 = pdf.get_y() - y_start
                
                pdf.set_xy(x_start + widths[0] + widths[1], y_start)
                pdf.multi_cell(widths[2], line_height, cols[2], 1, 'C', fill)
                h3 = pdf.get_y() - y_start
                
                pdf.set_xy(x_start + widths[0] + widths[1] + widths[2], y_start)
                pdf.multi_cell(widths[3], line_height, cols[3], 1, 'L', fill)
                h4 = pdf.get_y() - y_start
                
                max_h = max(h1, h2, h3, h4)
                pdf.set_xy(x_start, y_start + max_h)

        filename = f"MAST_Audit_{pkg_name}.pdf"
        pdf.output(filename)
        print(f"\n[+] Professional PDF generated: {filename}")
        return filename
    except Exception as e:
        print(f"[-] PDF error: {e}")
        return None

def perform_scan(apk_path, mode='3'):
    """Main scanning logic with modular analysis modes and colorized UI."""
    print_banner()
    
    if not os.path.exists(apk_path):
        print(f"{R}[!] CRITICAL: {apk_path} not found.{W}")
        return None, None

    print(f"{C}[*] Phase 1: Global Binary Analysis...{W}", end="\r")
    try:
        a = APK(apk_path)
        pkg = a.get_package()
        time.sleep(0.5)
        print(f"{G}[+] Phase 1: Binary Loaded ({os.path.basename(apk_path)}){W}")
    except Exception as e:
        print(f"{R}[!] Phase 1: Error parsing APK - {e}{W}")
        return None, None
    
    # Extraction Phase
    print(f"{C}[*] Phase 2: Manifest & Permissions Audit...{W}", end="\r")
    m_risks = extract_manifest_risks(a)
    print(f"{G}[+] Phase 2: Manifest Risk Profile Extracted          {W}")
    
    secrets = []
    if mode in ['2', '3']:
        print(f"{C}[*] Phase 3: Deep Dex Secret Scanning...{W}", end="\r")
        secrets = hunt_secrets(a)
        print(f"{G}[+] Phase 3: Deep Scan Complete ({len(secrets)} Secrets Found){W}")
    else:
        print(f"{Y}[-] Phase 3: Secret Scanning Skipped (Surface Mode){W}")
    
    print(f"{C}[*] Gathering Forensic App Context...{W}", end="\r")
    try:
        app_data = app(pkg, lang='en', country='us')
        title, desc = app_data.get('title', 'Unknown'), app_data.get('description', 'N/A')
        print(f"{G}[+] Forensic Context: {title} Verified              {W}")
    except:
        title, desc = "Unknown", "Offline analysis: No description available."
        print(f"{Y}[!] Forensic Context: Google Play Offline           {W}")

    # Audit Phase
    ai_report = ""
    is_mock = False
    
    if mode == '3':
        print(f"{C}[*] Phase 4: AI Logic Correlation...{W}", end="\r")
        ai_report = get_ai_audit(pkg, a.get_permissions(), desc, m_risks, secrets, title)
        
        if "AI_ERROR" in ai_report:
            print(f"{Y}[!] AI Restricted: Switching to Air-Gapped Heuristic Mode{W}")
            ai_report = get_mock_audit(pkg, a.get_permissions(), m_risks, secrets, title)
            is_mock = True
        else:
            print(f"{G}[+] Phase 4: AI Audit Successful                   {W}")
    else:
        print(f"{C}[*] Phase 4: Local Heuristic Reasoning...{W}", end="\r")
        ai_report = get_mock_audit(pkg, a.get_permissions(), m_risks, secrets, title)
        is_mock = True
        print(f"{G}[+] Phase 4: Static Reasoning Complete           {W}")

    summary = parse_summary(ai_report)
    mode_label = "AI-POWERED" if not is_mock else "LOCAL ENGINE"
    
    print("\n" + f"{B}{D}" + "-"*25 + f" {RESET}{B}{C}[ {mode_label} REPORT ]{RESET} " + f"{B}{D}" + "-"*25 + f"{RESET}")
    print(f"{C}[*] Package:   {W}{pkg}{RESET}")
    print(f"{G}[+] Risk Score: {summary['score']}/10{RESET}")
    print(f"{G}[+] Verdict:    {summary['verdict']}{RESET}")
    print(f"{C}[*] Findings:   {Y}{summary['findings']}{RESET}")
    if mode in ['2', '3']:
        print(f"{C}[*] Forensic Scan: {G}{len(secrets)} hardcoded entities found.{RESET}")
    print(f"{B}{D}" + "-" * 75 + f"{RESET}")

    choice = input(f"\n{Y}[?] Generate Detailed PDF Report? (y/n): {RESET}").lower()
    pdf_file = None
    if choice == 'y':
        print(f"{C}[*] Finalizing PDF Forensics...{RESET}")
        pdf_file = generate_pdf(pkg, title, ai_report)
        print(f"{G}[+] Audit Report Saved: {W}{pdf_file}{RESET}")
    
    return pdf_file, apk_path

def main():
    parser = argparse.ArgumentParser(description="Professional Mobile Security Auditor Pro")
    parser.add_argument("apk", nargs="?", help="Path to APK")
    args = parser.parse_args()

    # Initial Screen
    print_banner()

    current_apk = args.apk
    pdf_file = None

    # Acquisition Logic
    while True:
        if not current_apk:
            clear_screen()
            print_banner()
            print(f"{W}[?] Select APK Source:{RESET}")
            print(f" [{C}1{RESET}] Manual APK Path (Local)")
            print(f" [{C}2{RESET}] Select App from Phone (ADB)")
            src_choice = input(f"\n{Y}[?] Source > {RESET}").strip()
            
            if src_choice == '2':
                pkgs = get_adb_packages()
                if pkgs == "EXIT": continue
                if not pkgs: continue
                
                print(f"\n{B}{D}" + "-"*20 + f" {RESET}{B}{M}[ USER INSTALLED APPS ]{RESET} " + f"{B}{D}" + "-"*20 + f"{RESET}")
                for i, p in enumerate(pkgs[:40]):
                    print(f" [{C}{i+1:2d}{RESET}] {W}{p}{RESET}")
                print(f"{B}{D}" + "-" * 63 + f"{RESET}")
                
                pkg_idx = input(f"\n{Y}[?] Select package number (or '0' to back): {RESET}").strip()
                if pkg_idx == '0': continue
                try:
                    selected_pkg = pkgs[int(pkg_idx)-1]
                    current_apk = pull_apk_from_adb(selected_pkg)
                    if not current_apk: continue
                except:
                    print(f"{R}[!] Invalid Selection.{RESET}")
                    continue
            else:
                path_input = input(f"\n{Y}[?] Enter path to APK: {RESET}").strip().strip('"')
                if os.path.exists(path_input):
                    current_apk = path_input
                else:
                    print(f"{R}[!] File not found.{RESET}")
                    continue
        
        # Mode Selection
        clear_screen()
        print_banner()
        print(f"{W}[?] Select Analysis Depth:{RESET}")
        print(f" [{C}1{RESET}] {B}Surface Audit{RESET} (Manifest & Permissions - Fast)")
        print(f" [{C}2{RESET}] {B}Deep Static Audit{RESET} (Manifest + Secret Scanning - Local)")
        print(f" [{C}3{RESET}] {B}AI-Powered Contextual Audit{RESET} (Full Intelligence - Cloud)")
        
        mode = input(f"\n{Y}[?] Analysis Mode > {RESET}").strip()
        if mode not in ['1', '2', '3']: mode = '3'

        # Diagnostic Test only for AI mode
        if mode == '3':
            diag = diagnostic_connection_test()
            if diag == "KEY_ERROR": sys.exit(1)

        # Run Scan
        pdf_file, current_apk = perform_scan(current_apk, mode)

        # Master Post-Audit Menu
        while True:
            print(f"\n{B}{M}" + "="*20 + f" {RESET}{B}{W}[ MASTER CONTROL MENU ]{RESET} " + f"{B}{M}" + "="*20 + f"{RESET}")
            print(f" [{G}1{RESET}] Open PDF Report")
            print(f" [{C}2{RESET}] Change Analysis Mode (Same APK)")
            print(f" [{C}3{RESET}] New Audit (Different APK)")
            print(f" [{R}4{RESET}] Secure Wipe & Exit")
            
            choice = input(f"\n{Y}[?] Option > {RESET}").strip()
            
            if choice == '1':
                if pdf_file and os.path.exists(pdf_file):
                    if sys.platform == "win32": os.startfile(pdf_file)
                    else:
                        opener = "open" if sys.platform == "darwin" else "xdg-open"
                        subprocess.run([opener, pdf_file])
                else: print(f"{R}[!] No report file found.{RESET}")
            
            elif choice == '2':
                break # Break inner loop to show mode selection
                
            elif choice == '3':
                current_apk = None # Reset APK to trigger source selection
                break # Break inner loop
            
            elif choice == '4':
                if pdf_file and os.path.exists(pdf_file):
                    try: os.remove(pdf_file)
                    except: pass
                print(f"\n{G}[+] Secure Wipe Complete. Terminating Session...{RESET}")
                sys.exit(0)
            else:
                print(f"{R}[!] Invalid Option.{RESET}")
        
        if current_apk is None: continue # Back to acquisition
        else: continue # Back to mode selection (inner break choice 2)

if __name__ == "__main__":
    main()