import os
import shutil

# Define source and target directories
source_dir = r"C:\Users\RMDon\PycharmProjects\FSR_c_%\Business_Assets_To_Move\png_assets"
target_dir = r"C:\Users\RMDon\PycharmProjects\FSR_c_%\static\images\nba_charts"

# Create target directory if it doesn't exist
if not os.path.exists(target_dir):
    os.makedirs(target_dir)
    print(f"Created directory: {target_dir}")

# Check if source directory exists
if os.path.exists(source_dir):
    # Move files
    for filename in os.listdir(source_dir):
        if filename.lower().endswith(".png"):
            source_file = os.path.join(source_dir, filename)
            target_file = os.path.join(target_dir, filename)
            try:
                shutil.move(source_file, target_file)
                print(f"Moved: {filename}")
            except Exception as e:
                print(f"Error moving {filename}: {e}")
    print("Migration complete.")
else:
    print(f"Source directory {source_dir} does not exist. Skipping migration.")