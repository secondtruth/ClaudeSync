import sys
import os
import traceback

output_file = "test_output.txt"

try:
    with open(output_file, 'w') as f:
        f.write("Starting test...\n")
        f.write(f"Python version: {sys.version}\n")
        f.write(f"Current directory: {os.getcwd()}\n")
        f.write(f"Python path: {sys.path}\n\n")
        
        # Test ClaudeSync import
        try:
            import claudesync
            f.write("✓ ClaudeSync imported successfully\n")
            f.write(f"  Location: {claudesync.__file__}\n")
        except ImportError as e:
            f.write(f"✗ Failed to import claudesync: {e}\n")
            f.write("  Trying pip install...\n")
            import subprocess
            result = subprocess.run([sys.executable, "-m", "pip", "install", "-e", "."], 
                                    capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            f.write(f"  Install result: {result.returncode}\n")
            f.write(f"  Stdout: {result.stdout}\n")
            f.write(f"  Stderr: {result.stderr}\n")
        
        # Test GUI import
        try:
            from auth_handler import AuthHandler
            f.write("✓ AuthHandler imported successfully\n")
        except Exception as e:
            f.write(f"✗ Failed to import AuthHandler: {e}\n")
            f.write(f"  Traceback:\n{traceback.format_exc()}\n")
        
        f.write("\nTest complete!\n")
        
except Exception as e:
    with open(output_file, 'w') as f:
        f.write(f"Fatal error: {e}\n")
        f.write(f"Traceback:\n{traceback.format_exc()}\n")

print(f"Test output written to: {output_file}")
