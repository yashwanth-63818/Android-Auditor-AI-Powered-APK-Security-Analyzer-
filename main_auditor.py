import warnings
warnings.filterwarnings("ignore")
import os
import sys
import argparse
import re
import datetime
import subprocess
import socket
import requests
import json
import time
from colorama import Fore, Style, init
init(autoreset=True)
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
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
except ImportError:
    print("[-] Error: ReportLab not found. Run 'pip install reportlab'")
    sys.exit(1)

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
            print(f"\n{B}{R}[!] ERROR: NO DEVICE DETECTED.{W}")
            print(f"{Y} [R] Retry | [B] Back to Menu{W}")
            sub_choice = input(f"\n{Y}[?] Choice: {W}").strip().upper()
            if sub_choice == 'R':
                continue
            return "BACK"
        
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
    """Diagnostic check for Gemini API status and Key validity via REST API."""
    if not GEMINI_API_KEY:
        print(f"\n{B}{R}[!] CRITICAL: Missing GEMINI_API_KEY in .env file.{W}")
        return False

    print(f"{C}[*] Performing Diagnostic Connection Test...{W}")
    
    if not is_google_reachable():
        print(f"{R}[!] Diagnostic: 8.8.8.8 Unreachable. Check your network/proxy.{W}")
        return "NETWORK_ERROR"

    print(f"{C}[*] Synchronizing with Gemini 1.5 Flash... {W}", end="", flush=True)
    
    try:
        for version in ['v1beta', 'v1']:
            url = f"https://generativelanguage.googleapis.com/{version}/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
            payload = {"contents": [{"parts": [{"text": "ping"}]}]}
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                print(f"{G}[Connected]{W}")
                print(f"{G}[+] Diagnostic: Gemini API is LIVE and Key is VALID.{W}")
                return True
        
        print(f"{R}[Failed]{W}")
        return "AI_OFFLINE"
    except Exception as e:
        print(f"{R}[Error]{W}")
        print(f"{R}[!] Diagnostic: Connection failed - {e}{W}")
        return "AI_OFFLINE"

# --- PDF LOGIC (REPORTLAB) ---

def generate_pdf(pkg_name, app_title, ai_response, secrets=[], pdf_type="full"):
    """Generates a professional VAPT report using ReportLab with tiered depth."""
    filename = f"MAST_Audit_{pkg_name}.pdf"
    abs_path = os.path.abspath(filename)
    
    # Severity & Remediation Metadata for Secrets
    SECRETS_METADATA = {
        "Google API Key": {"sev": "High", "rem": "Restrict API Key in GCP Console to specific IP/Package."},
        "Firebase URL": {"sev": "Medium", "rem": "Check Firebase Security Rules & Database Permissions."},
        "AWS Access Key": {"sev": "High", "rem": "Revoke Key immediately and rotate via IAM."},
        "AWS S3 Bucket": {"sev": "Medium", "rem": "Ensure S3 bucket is private and ACLs are locked down."},
        "Private IP/URL": {"sev": "Low", "rem": "Ensure internal IPs aren't exposed in production builds."},
        "Sensitive Keyword": {"sev": "Medium", "rem": "Replace with Android Keystore or Encrypted Storage."}
    }
    
    # Configuration for Letter pagesize and margins
    doc = SimpleDocTemplate(abs_path, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    
    # Professional Custom Styles
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=24, textColor=colors.HexColor("#1B2631"), alignment=TA_CENTER, spaceAfter=12)
    sub_style = ParagraphStyle('SubStyle', parent=styles['Normal'], fontSize=11, textColor=colors.grey, alignment=TA_CENTER, spaceAfter=24)
    section_style = ParagraphStyle('SectionStyle', parent=styles['Heading2'], fontSize=16, textColor=colors.HexColor("#1B2631"), spaceBefore=20, spaceAfter=12)
    normal_style = styles['Normal']
    
    # Header Section
    elements.append(Paragraph("MOBILE VAPT AUDITOR: SECURITY REPORT", title_style))
    elements.append(Paragraph(f"Enterprise Grade Binary Forensics | {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}", sub_style))
    elements.append(Spacer(1, 12))
    
    elements.append(Paragraph(f"<b>Target Application:</b> {app_title}", normal_style))
    elements.append(Paragraph(f"<b>Package Name:</b> {pkg_name}", normal_style))
    elements.append(Spacer(1, 24))
    
    clean_report = ai_response.replace('\x00', '') # Sanitize
    
    # 1. Executive Summary
    elements.append(Paragraph("1. Security Analysis Overview", section_style))
    summary_match = re.search(r"SUMMARY_START(.*?)SUMMARY_END", clean_report, re.DOTALL | re.IGNORECASE)
    if summary_match:
        summary_text = summary_match.group(1).strip().replace("\n", "<br/>")
        elements.append(Paragraph(summary_text, normal_style))
    elements.append(Spacer(1, 24))
    
    # 2. Forensic Findings Table
    elements.append(Paragraph("2. Detailed Findings & Remediation Guide", section_style))
    
    # Define table header and cell styles with wrapping support
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=10, textColor=colors.white, fontName='Helvetica-Bold')
    cell_style = ParagraphStyle('CellStyle', parent=styles['Normal'], fontSize=9, leading=11)
    
    data = [[
        Paragraph("<b>Component / Vulnerability</b>", header_style),
        Paragraph("<b>Contextual Risk Analysis</b>", header_style),
        Paragraph("<b>OWASP Cat.</b>", header_style),
        Paragraph("<b>Remediation Guide</b>", header_style)
    ]]
    
    table_match = re.search(r"TABLE_START(.*?)TABLE_END", clean_report, re.DOTALL | re.IGNORECASE)
    if table_match:
        rows = table_match.group(1).strip().split("\n")
        for row in rows:
            if "|" not in row: continue
            cols = [c.strip() for c in row.split("|")]
            if len(cols) >= 4:
                # Wrap each cell in a Paragraph for automatic text wrapping
                wrapped_row = [Paragraph(col, cell_style) for col in cols[:4]]
                data.append(wrapped_row)
    
    # Table Alignment: Total 540 pts (Letter width 612 - 60 margin)
    t = Table(data, colWidths=[120, 180, 80, 160], repeatRows=1)
    
    # Enterprise Table Styling: Dark Blue Header, White Text, Grey Grid Lines
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1B2631")), # Enterprise Dark Blue
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ])
    
    # Alternate Row Shading
    for i in range(1, len(data)):
        if i % 2 == 0:
            style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor("#F2F4F4"))
    
    t.setStyle(style)
    elements.append(t)
    
    # 3. Hardcoded Secrets Found (Forensic Scan result)
    if secrets:
        elements.append(Spacer(1, 24))
        title_suffix = "(Executive Summary)" if pdf_type == "summary" else "(Full Forensic Trail)"
        elements.append(Paragraph(f"3. Hardcoded Secrets Found {title_suffix}", section_style))
        
        sec_header_style = ParagraphStyle('SecHeader', parent=styles['Normal'], fontSize=9, textColor=colors.white, fontName='Helvetica-Bold')
        sec_cell_style = ParagraphStyle('SecCell', parent=styles['Normal'], fontSize=8, leading=10)
        
        # New Column structure: Type, Evidence, Severity, Remediation
        sec_data = [[
            Paragraph("<b>Secret Type</b>", sec_header_style), 
            Paragraph("<b>Evidence (Match)</b>", sec_header_style),
            Paragraph("<b>Severity</b>", sec_header_style),
            Paragraph("<b>Remediation Guide</b>", sec_header_style)
        ]]
        
        # Filtering for Executive Summary
        filtered_secrets = secrets
        if pdf_type == "summary":
            # Pick High Risk first, then Medium, up to 15
            high_risk = [s for s in secrets if SECRETS_METADATA.get(s['type'], {}).get('sev') == "High"]
            med_risk = [s for s in secrets if SECRETS_METADATA.get(s['type'], {}).get('sev') == "Medium"]
            low_risk = [s for s in secrets if SECRETS_METADATA.get(s['type'], {}).get('sev') == "Low"]
            filtered_secrets = (high_risk + med_risk + low_risk)[:15]

        for s in filtered_secrets:
            meta = SECRETS_METADATA.get(s['type'], {"sev": "Medium", "rem": "Apply secure coding practices."})
            
            # Color coding for severity
            sev_color = "#943126" if meta['sev'] == "High" else ("#7E5109" if meta['sev'] == "Medium" else "#1B4F72")
            sev_p = Paragraph(f"<font color='{sev_color}'><b>{meta['sev']}</b></font>", sec_cell_style)
            
            sec_data.append([
                Paragraph(s['type'], sec_cell_style), 
                Paragraph(s['match'][:150] + ("..." if len(s['match']) > 150 else ""), sec_cell_style),
                sev_p,
                Paragraph(meta['rem'], sec_cell_style)
            ])
        
        # Consistent column widths: [120, 180, 80, 160]
        st = Table(sec_data, colWidths=[110, 190, 75, 165], repeatRows=1)
        st_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1B2631")), 
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
        ])
        
        for i in range(1, len(sec_data)):
            if i % 2 == 0:
                st_style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor("#F2F2F2"))
        
        st.setStyle(st_style)
        elements.append(st)
        
        if pdf_type == "summary" and len(secrets) > 15:
            elements.append(Spacer(1, 6))
            elements.append(Paragraph(f"<i>[!] Note: Showing top 15 critical findings. Total {len(secrets)} secrets detected in full scan.</i>", sub_style))
        elif len(secrets) > 0:
            elements.append(Spacer(1, 6))
            elements.append(Paragraph(f"<i>Total forensic entities detected: {len(secrets)}</i>", sub_style))

    # Final Footer
    elements.append(Spacer(1, 40))
    elements.append(Paragraph("<i>End of Forensic Security Audit. Confidential Document.</i>", sub_style))
    
    # File Lock Handling with Retry Loop
    while True:
        try:
            doc.build(elements)
            print(f"\n{G}[+] Professional PDF generated at: {abs_path}{W}")
            return abs_path
        except PermissionError:
            print(f"\n{B}{R}[!] CRITICAL: Close the PDF file '{filename}' and press Enter to retry.{RESET}")
            input(f"{Y}[?] Press Enter to continue...{RESET}")
        except Exception as e:
            print(f"{R}[-] PDF Generation Failed: {e}{W}")
            return None

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
    """Performs deep AI analysis using direct REST API."""
    if not GEMINI_API_KEY:
        return "ERROR: Missing GEMINI_API_KEY in .env"

    if not is_google_reachable():
        return "AI_ERROR: No Internet Connection."

    print(f"{C}[*] Synchronizing with Gemini 1.5 Flash... {W}", end="", flush=True)
    
    prompt = f"""
    ROLE: Senior Mobile Security Auditor.
    TASK: Perform a professional VAPT analysis of the following Android APK data.
    
    APP DATA:
    App Name: {app_title}
    Package: {package}
    Permissions: {', '.join(permissions)}
    Secrets Found: {len(secrets)}
    
    SECURITY CONTEXT:
    Manifest Risks: {manifest_risks}
    Dex Secrets: {secrets[:10]}
    
    GOAL:
    1. Identify misalignment between App Name and Permissions.
    2. Map findings to OWASP Mobile Top 10.
    3. Provide remediation steps.

    FORMAT:
    SUMMARY_START
    RISK SCORE: [0-10]
    VERDICT: [Safe/Suspicious/Malicious]
    TOP FINDINGS: [Summary]
    SUMMARY_END

    TABLE_START
    Vulnerability | Contextual Risk Analysis | OWASP Category | Remediation Steps
    ...
    TABLE_END
    """

    try:
        # Fallback logic: Try v1beta first, then v1
        for version in ['v1beta', 'v1']:
            url = f"https://generativelanguage.googleapis.com/{version}/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            resp = requests.post(url, json=payload, timeout=60)
            
            if resp.status_code == 200:
                print(f"{G}[Connected]{W}")
                data = resp.json()
                return data['candidates'][0]['content']['parts'][0]['text'].strip()
        
        print(f"{R}[Failed]{W}")
        return f"AI_ERROR: Model 404 or connection failed."
            
    except Exception as e:
        print(f"{R}[Offline]{W}")
        return f"AI_ERROR: {e}"

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
    except Exception:
        title, desc = "Unknown", "Offline analysis: No description available."
        print(f"{Y}[!] Forensic Context: Google Play Offline / Limited Info{W}")

    # Audit Phase
    ai_report = ""
    is_mock = False
    
    if mode == '3':
        ai_report = get_ai_audit(pkg, a.get_permissions(), desc, m_risks, secrets, title)
        
        if "AI_ERROR" in ai_report or "ERROR" in ai_report.upper():
            print(f"{Y}[!] AI Restricted: Switching to [!] Air-Gapped Heuristic Mode{W}")
            ai_report = get_mock_audit(pkg, a.get_permissions(), m_risks, secrets, title)
            is_mock = True
        else:
            print(f"{G}[+] Phase 4: AI Analysis Complete                       {W}")
    else:
        print(f"{C}[*] Phase 4: Local Heuristic Reasoning...{W}", end="\r")
        ai_report = get_mock_audit(pkg, a.get_permissions(), m_risks, secrets, title)
        is_mock = True
        print(f"{G}[+] Phase 4: Static Reasoning Complete           {W}")

    summary = parse_summary(ai_report)
    mode_label = "AI-POWERED VAPT" if not is_mock else "LOCAL HEURISTIC"
    
    print("\n" + f"{B}{M}" + "="*25 + f" {RESET}{B}{C}[ {mode_label} REPORT ]{RESET} " + f"{B}{M}" + "="*25 + f"{RESET}")
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
        print(f"\n{W}[?] Select Report Scope:{RESET}")
        print(f" [{C}1{RESET}] Executive Summary (Critical Findings Only)")
        print(f" [{C}2{RESET}] Full Forensic Report (All {len(secrets)} Findings)")
        
        scope_choice = input(f"\n{Y}[?] Scope > {RESET}").strip()
        pdf_type = "summary" if scope_choice == '1' else "full"
        
        print(f"{C}[*] Finalizing PDF Forensics ({pdf_type.upper()})...{RESET}")
        pdf_file = generate_pdf(pkg, title, ai_report, secrets, pdf_type)
        print(f"{G}[+] Audit Report Saved: {W}{pdf_file}{RESET}")
    
    return pdf_file, apk_path

def main():
    while True:
        clear_screen()
        print_banner()
        
        # Clean Prompt at Startup
        cmd = input(f"{W}[?] Type {G}'start'{W} to begin audit or {R}'end'{W} to exit: {RESET}").strip().lower()
        
        if cmd == 'end':
            print(f"\n{B}{R}[+] Terminating Session...{RESET}")
            sys.exit(0)
        
        if cmd != 'start':
            print(f"{R}[!] Invalid Command. Please type 'start' or 'end'.{RESET}")
            time.sleep(1)
            continue

        # Reset session variables
        current_pdf_report = None
        current_apk = None

        # Acquisition Loop
        while True:
            clear_screen()
            print_banner()
            print(f"{W}[?] Select APK Source:{RESET}")
            print(f" [{C}1{RESET}] Manual APK Path (Local)")
            print(f" [{C}2{RESET}] Select App from Phone (ADB)")
            print(f" [{Y}B{RESET}] Back to Main Menu")
            
            src_choice = input(f"\n{Y}[?] Source > {RESET}").strip().upper()
            
            if src_choice == 'B':
                break

            if src_choice == '2':
                pkgs = get_adb_packages()
                if pkgs == "BACK": continue
                if not pkgs: continue
                
                clear_screen()
                print_banner()
                print(f"{B}{D}" + "-"*20 + f" {RESET}{B}{M}[ USER INSTALLED APPS ]{RESET} " + f"{B}{D}" + "-"*20 + f"{RESET}")
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
                    time.sleep(1)
                    continue
            else:
                path_input = input(f"\n{Y}[?] Enter path to APK (or 'B' to go back): {RESET}").strip().strip('"')
                if path_input.upper() == 'B': continue
                if os.path.exists(path_input):
                    current_apk = os.path.abspath(path_input)
                else:
                    print(f"{R}[!] File not found.{RESET}")
                    time.sleep(1)
                    continue
            
            # If APK acquired, proceed to Mode Selection
            if current_apk:
                clear_screen()
                print_banner()
                print(f"{W}[?] Select Analysis Depth:{RESET}")
                print(f" [{C}1{RESET}] Surface Audit (Manifest)")
                print(f" [{C}2{RESET}] Deep Static Audit (Manifest + Secrets)")
                print(f" [{C}3{RESET}] AI Contextual Audit (Full Logic via Gemini v1)")
                
                mode = input(f"\n{Y}[?] Analysis Mode > {RESET}").strip()
                if mode not in ['1', '2', '3']: mode = '3'

                # Diagnostic Test only for AI mode
                if mode == '3':
                    diag = diagnostic_connection_test()
                    if diag == "KEY_ERROR": sys.exit(1)

                # Run Scan
                # Ensure current_pdf_report stores absolute path and doesn't wipe previous if scan fails
                new_pdf, _ = perform_scan(current_apk, mode)
                if new_pdf:
                    current_pdf_report = new_pdf

                # Master Control Menu (Loop until New Scan or Exit)
                while True:
                    print(f"\n{B}{M}" + "="*25 + f" {RESET}{B}{W}[ MASTER CONTROL MENU ]{RESET} " + f"{B}{M}" + "="*25 + f"{RESET}")
                    print(f" [{G}1{RESET}] {W}Open PDF Report{RESET}")
                    print(f" [{C}2{RESET}] {W}Reset (Different App in this session){RESET}")
                    print(f" [{Y}3{RESET}] {W}Delete Report & Return to Start{RESET}")
                    print(f" [{R}4{RESET}] {W}Exit Auditor{RESET}")
                    
                    choice = input(f"\n{Y}[?] Option > {RESET}").strip()
                    
                    if choice == '1':
                        if current_pdf_report and os.path.exists(current_pdf_report):
                            print(f"{G}[*] Launching: {current_pdf_report}{RESET}")
                            if sys.platform == "win32": 
                                os.startfile(current_pdf_report)
                            else:
                                opener = "open" if sys.platform == "darwin" else "xdg-open"
                                subprocess.run([opener, current_pdf_report])
                        else: 
                            print(f"{R}[!] No report available to open at: {current_pdf_report}{RESET}")
                    
                    elif choice == '2':
                        current_apk = None 
                        break # Break from master menu to go back to Acquisition logic
                    
                    elif choice == '3':
                        if current_pdf_report and os.path.exists(current_pdf_report):
                            try: 
                                os.remove(current_pdf_report)
                                print(f"\n{G}[+] Secure Wipe Complete.{RESET}")
                                current_pdf_report = None
                            except PermissionError:
                                print(f"\n{R}[!] ERROR: Permission Denied. Close the PDF report before deleting!{RESET}")
                                continue
                        else:
                            print(f"\n{Y}[-] No report found to delete.{RESET}")
                        current_apk = None
                        break # Break from master menu to go back to Acquisition logic
                    
                    elif choice == '4':
                        print(f"\n{B}{R}[+] Terminating Session...{RESET}")
                        sys.exit(0)
                    else:
                        print(f"{R}[!] Invalid Option.{RESET}")
                
                # After breaking from master control menu, we go back to the top of acquisition loop
                # If current_apk is None, it will prompt for source again.
                if current_apk is None:
                    continue


if __name__ == "__main__":
    main()