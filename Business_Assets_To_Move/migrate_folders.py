import os
import shutil

# Define the source directory and the target subdirectory
source_dir = r"C:\Users\RMDon\PycharmProjects\FSR_c_%\Business_Assets_To_Move"
target_subdir = os.path.join(source_dir, "png_assets")

# Create the target subdirectory if it doesn't exist
if not os.path.exists(target_subdir):
    os.makedirs(target_subdir)
    print(f"Created directory: {target_subdir}")

# Iterate through files in the source directory
for filename in os.listdir(source_dir):
    # Check if the file is a PNG
    if filename.lower().endswith(".png"):
        source_file = os.path.join(source_dir, filename)
        target_file = os.path.join(target_subdir, filename)
        
        # Move the file
        try:
            shutil.move(source_file, target_file)
            print(f"Moved: {filename}")
        except Exception as e:
            print(f"Error moving {filename}: {e}")

print("Migration complete.")