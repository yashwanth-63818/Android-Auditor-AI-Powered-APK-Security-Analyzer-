import sys
import os
from androguard.core.apk import APK

def extract_apk_info(apk_path):
    """
    Extracts the package name and permissions from an Android APK file using androguard.
    """
    if not os.path.exists(apk_path):
        print(f"Error: The file '{apk_path}' does not exist.")
        return

    try:
        print(f"Analyzing {apk_path}...")
        # Load the APK file
        a = APK(apk_path)
        
        # Get Package Name
        package_name = a.get_package()
        
        # Get Permissions
        permissions = a.get_permissions()
        
        # Print Results
        print("\n" + "="*50)
        print("APK ANALYSIS RESULTS")
        print("="*50)
        print(f"{'Package Name:':<15} {package_name}")
        print("-" * 50)
        print(f"Permissions Found ({len(permissions)}):")
        
        if permissions:
            # Sort permissions for better readability
            for permission in sorted(permissions):
                print(f"  - {permission}")
        else:
            print("  No permissions requested by this APK.")
            
        print("="*50)
        
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    # Check if a file path was provided as a command-line argument
    if len(sys.argv) > 1:
        apk_input = sys.argv[1]
    else:
        # Prompt the user for input if no argument is provided
        apk_input = input("Please enter the path to the APK file: ").strip().strip('"').strip("'")
    
    if apk_input:
        extract_apk_info(apk_input)
    else:
        print("No APK path provided. Exiting.")
