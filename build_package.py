import subprocess
import sys

def install_build_tools():
    print("Installing build tools...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "wheel", "setuptools"])

def build_package():
    print("Building the package...")
    # Run 'python setup.py sdist bdist_wheel'
    subprocess.check_call([sys.executable, "setup.py", "sdist", "bdist_wheel"])

if __name__ == "__main__":
    try:
        install_build_tools()
        build_package()
        print("\nSUCCESS: Package built successfully!")
        print("Check the 'dist/' directory for your .tar.gz and .whl files.")
    except subprocess.CalledProcessError as e:
        print(f"\nERROR: Build failed with error code {e.returncode}")
