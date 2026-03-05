import os
import sys
from google import genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get Gemini API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def analyze_app_safety(permissions, description):
    """
    Analyzes whether Android permissions are justified given an app's description
    using Google's latest genai SDK. Returns a formatted security report.
    """
    if not GEMINI_API_KEY:
        return "Error: GEMINI_API_KEY not found in .env file or environment."

    try:
        # Initialize the GenAI Client
        client = genai.Client(api_key=GEMINI_API_KEY)
        
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

        # Generate response using gemini-2.0-flash
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt
        )
        
        if response and response.text:
            return response.text.strip()
        else:
            return "Error: Received an empty response from Gemini AI."
            
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

    print("Running Security Audit with Gemini 2.0 Flash...\n")
    analysis_report = analyze_app_safety(test_permissions, test_description)
    
    print("="*60)
    print("SECURITY ANALYSIS REPORT")
    print("="*60)
    print(analysis_report)
    print("="*60)
