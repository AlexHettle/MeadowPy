# Virtual Environments & Packages
# Virtual environments keep project dependencies separate.

# === What is a virtual environment? ===
# It's an isolated Python installation for your project.
# Each project can have its own packages without conflicts.

# === Creating and using a venv (run in terminal) ===
# Step 1: Create a virtual environment
#   python -m venv .venv
#
# Step 2: Activate it
#   Windows:  .venv\Scripts\activate
#   Mac/Linux: source .venv/bin/activate
#
# Step 3: Install packages
#   pip install requests
#
# Step 4: Deactivate when done
#   deactivate

# === Useful pip commands ===
print("Common pip commands:")
print("  pip install <package>      Install a package")
print("  pip install -r req.txt     Install from file")
print("  pip list                   Show installed packages")
print("  pip freeze > req.txt       Save dependencies")
print("  pip uninstall <package>    Remove a package")

# === Let's check what's installed right now ===
import pkg_resources

installed = sorted(
    [(d.project_name, d.version)
     for d in pkg_resources.working_set],
    key=lambda x: x[0].lower()
)

print(f"\nInstalled packages ({len(installed)}):")
for name, version in installed[:10]:
    print(f"  {name:30} {version}")
if len(installed) > 10:
    print(f"  ... and {len(installed) - 10} more")

# === Tip: MeadowPy can create venvs for you! ===
# Go to Run > Configure Interpreter > Create Virtual Environment
