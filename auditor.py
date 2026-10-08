import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

raw_key = os.getenv("GROQ_API_KEY", "").strip().replace('"', '')
client = OpenAI(api_key=raw_key, base_url="https://api.groq.com/openai/v1")

def analyze_app_safety(permissions, description):
    """
    Analyzes whether Android permissions are justified given an app's description
    using Google's latest genai SDK. Returns a formatted security report.
    """
    if not raw_key:
        return "Error: GROQ_API_KEY not found in .env file or environment."

    try:
        
        # Prepare the structured prompt for a consistent report format
        prompt = f"""
        Role: Mobile Security Analyst.
        Task: Analyze the safety of an Android application by checking if its requested permissions are justified by its description.
        
        APP DESCRIPTION:
        \"\"\"{description}\"\"\"
        
        REQUESTED PERMISSIONS:
        {", ".join(permissions)}
        
        REQUIRED OUTPUT FORMAT (Return exactly in this format):
        
        Risk Score (1 to 10): 
        [Provide a numeric score]
        
        Suspicious Permissions: 
        - [Permission Name]: [Reason why it's suspicious or 'None']
        
        AI Verdict: 
        [A brief explanation of whether the app seems safe, suspicious, or malicious based on the alignment (or lack thereof) between permissions and features.]
        """

        # Generate response using Groq (Llama-3)
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama3-8b-8192",
        )
        
        if chat_completion.choices:
            content = chat_completion.choices[0].message.content
            return content.strip() if content else ""
        else:
            return "Error: Received an empty response from Groq AI."
            
    except Exception as e:
        return f"An unexpected error occurred during AI analysis: {str(e)}"

if __name__ == "__main__":
    # Test cases
    test_permissions = [
        "android.permission.INTERNET",
        "android.permission.ACCESS_FINE_LOCATION",
        "android.permission.CAMERA"
    ]
    
    test_description = "Explore and navigate the world with confidence using Google Maps. Find the best routes with live traffic data..."

    # TrueColor ANSI escape sequences
    PHOSPHOR_GREEN = '\033[38;2;15;255;80m\033[1m'
    NEON_RED = '\033[38;2;255;20;20m\033[1m'
    
    # Enable ANSI escape sequences on Windows
    import os
    if os.name == 'nt':
        os.system('color')

    print(f"{PHOSPHOR_GREEN}Synchronizing with Groq Llama-3...\n")
    analysis_report = analyze_app_safety(test_permissions, test_description)
    
    print(f"{NEON_RED}="*60)
    print(f"{NEON_RED}SECURITY ANALYSIS REPORT")
    print(f"{NEON_RED}="*60)
    print(f"{NEON_RED}{analysis_report}")
    print(f"{NEON_RED}="*60)
