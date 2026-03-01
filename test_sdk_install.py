import os
import subprocess
import sys
import shutil

def test_sdk():
    print("--- STARTING SDK VERIFICATION ---")
    
    # 1. Locate the .whl file
    dist_dir = os.path.join(os.getcwd(), "dist")
    if not os.path.exists(dist_dir):
        print("ERROR: 'dist' directory not found. Did you run build_package.py?")
        return

    whl_files = [f for f in os.listdir(dist_dir) if f.endswith(".whl")]
    if not whl_files:
        print("ERROR: No .whl file found in 'dist'.")
        return
    
    whl_path = os.path.join(dist_dir, whl_files[0])
    print(f"Found Package: {whl_files[0]}")

    # 2. Create a temporary test script
    # This script mimics what a client would write
    client_script_content = """
import sys
try:
    from fsr import calculate_predictability
    from sliding_window import calculate_sliding_window
    
    data = [10, 12, 11, 10.5, 11.2, 10.8, 12.1, 11.5]
    
    print("\\n--- CLIENT SCRIPT OUTPUT ---")
    score = calculate_predictability(data, k=1.0)
    print(f"Predictability Score: {score:.2f}%")
    
    windows = calculate_sliding_window(data, window_size=3, k=1.0)
    print(f"Sliding Windows Calculated: {len(windows)}")
    print("--- END CLIENT SCRIPT ---")
    
except ImportError as e:
    print(f"IMPORT ERROR: {e}")
    sys.exit(1)
except Exception as e:
    print(f"RUNTIME ERROR: {e}")
    sys.exit(1)
"""
    client_script_path = "client_test_script.py"
    with open(client_script_path, "w") as f:
        f.write(client_script_content)

    # 3. Create a virtual environment (The "Clean Room")
    venv_dir = "test_env"
    if os.path.exists(venv_dir):
        shutil.rmtree(venv_dir)
    
    print("Creating clean virtual environment...")
    subprocess.check_call([sys.executable, "-m", "venv", venv_dir])

    # Determine pip path inside venv
    if os.name == 'nt': # Windows
        pip_exe = os.path.join(venv_dir, "Scripts", "pip")
        python_exe = os.path.join(venv_dir, "Scripts", "python")
    else: # Mac/Linux
        pip_exe = os.path.join(venv_dir, "bin", "pip")
        python_exe = os.path.join(venv_dir, "bin", "python")

    # 4. Install the SDK into the clean environment
    print("Installing SDK into virtual environment...")
    subprocess.check_call([pip_exe, "install", whl_path])

    # 5. Run the client script using the venv's python
    print("Running client test script...")
    try:
        subprocess.check_call([python_exe, client_script_path])
        print("\n✅ VERIFICATION SUCCESSFUL: The SDK is installed and working!")
    except subprocess.CalledProcessError:
        print("\n❌ VERIFICATION FAILED: The client script crashed.")
    finally:
        # Cleanup
        if os.path.exists(client_script_path):
            os.remove(client_script_path)
        # We leave the venv for inspection if needed, or you can delete it manually

if __name__ == "__main__":
    test_sdk()
