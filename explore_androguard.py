from androguard.core.apk import APK
import os

apk_path = "test.apk"
if os.path.exists(apk_path):
    a = APK(apk_path)
    print("\n[+] APK Object attributes/methods:")
    for attr in dir(a):
        if not attr.startswith("_"):
            print(attr)
else:
    print("test.apk not found")
