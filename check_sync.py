import datetime
import time
import ssl
import socket

def check_environmental_health():
    print(f"--- Predictability API v1.01 Sync Check ---")
    
    # 1. Check Local Python Time
    now = datetime.datetime.now()
    print(f"Python Local Time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 2. Check SSL Handshake with Google (Test if certificates work)
    try:
        context = ssl.create_default_context()
        with socket.create_connection(('google.com', 443)) as sock:
            with context.wrap_socket(sock, server_hostname='google.com') as ssock:
                print(f"✅ SSL Handshake: SUCCESS (Local certificates are valid)")
    except Exception as e:
        print(f"❌ SSL Handshake: FAILED. Reason: {e}")
        print("   (This usually means your PC clock is so far off that certificates look expired)")

if __name__ == "__main__":
    check_environmental_health()
