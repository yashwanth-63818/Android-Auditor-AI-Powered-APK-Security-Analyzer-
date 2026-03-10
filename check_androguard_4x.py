try:
    from androguard.core.bytecodes.dvm import DalvikVMFormat
    print("Found DalvikVMFormat at androguard.core.bytecodes.dvm")
except ImportError:
    try:
        from androguard.core.dex import DalvikVMFormat
        print("Found DalvikVMFormat at androguard.core.dex")
    except ImportError:
        print("DalvikVMFormat not found")
