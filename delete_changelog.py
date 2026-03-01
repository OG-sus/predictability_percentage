import os

if os.path.exists("CHANGELOG.md"):
    os.remove("CHANGELOG.md")
    print("Deleted CHANGELOG.md")
else:
    print("CHANGELOG.md not found")
