import sys
from google_play_scraper import app

def fetch_app_details(package_name):
    """
    Fetches the App Title, Description, and Category using google-play-scraper.
    """
    try:
        print(f"Fetching details for package: {package_name}...\n")
        
        # Fetch the app details
        result = app(package_name)
        
        # Extract required fields
        title = result.get('title', 'N/A')
        description = result.get('description', 'N/A')
        genre = result.get('genre', 'N/A')
        
        # Clean up description (optional: limit length for display)
        short_description = (description[:200] + '...') if len(description) > 200 else description

        # Print the results clearly
        print("=" * 60)
        print("GOOGLE PLAY STORE APP DETAILS")
        print("=" * 60)
        print(f"{'App Title:':<15} {title}")
        print(f"{'Category:':<15} {genre}")
        print("-" * 60)
        print("Description:")
        print(description)
        print("=" * 60)
        
    except Exception as e:
        print(f"Error: Could not find app or fetch details for '{package_name}'.")
        print(f"Details: {e}")

if __name__ == "__main__":
    # Use provided package name or take from arguments
    package_to_search = "com.google.android.apps.maps"
    
    fetch_app_details(package_to_search)
