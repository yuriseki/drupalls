"""
Setup command for Phpactor dependency.
"""

import subprocess
import sys
from pathlib import Path

def main():
    """Main setup function."""
    project_root = Path(__file__).parent.parent.parent
    setup_script = project_root / "scripts" / "setup_phpactor.sh"

    if not setup_script.exists():
        print("ERROR: Setup script not found")
        sys.exit(1)

    # Run setup script
    result = subprocess.run(["bash", str(setup_script)], cwd=str(project_root))

    if result.returncode == 0:
        print("✓ Phpactor CLI setup complete")
        print("You can now use type checking features in DrupalLS")
    else:
        print("✗ Phpactor setup failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
