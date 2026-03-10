try:
    from androguard.core.dex import DEX
    print("Found DEX at androguard.core.dex")
except ImportError:
    print("DEX not found in androguard.core.dex")
