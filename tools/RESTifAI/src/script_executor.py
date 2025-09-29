import subprocess
import os

from config import PROJECT_ROOT

class ScriptExecutor:
    """Simple script executor for database reset or other operations"""
    
    # Valid script file extensions
    VALID_EXTENSIONS = {
        '.py': 'python',
        '.ps1': 'powershell', 
        '.bat': 'batch',
        '.cmd': 'batch',
        '.sh': 'bash'
    }
    
    def __init__(self, script_path: str):
        self.script_path = script_path
        self.working_directory = PROJECT_ROOT
        self.timeout = 300

    def get_extension(self) -> str:
        """Get the file extension of the script path"""
        if not self.script_path:
            return ""
        _, ext = os.path.splitext(self.script_path.lower())
        return ext
    
    def is_valid_script_file(self) -> tuple[bool, str]:
        """
        Check if the file is a valid script file
        
        Args:
            file_path: Path to check (uses self.script_path if None)
            
        Returns:
            tuple: (is_valid, error_message)
        """
        if not self.script_path:
            return False, "No script path provided"
            
        if not os.path.exists(self.script_path):
            return False, f"File does not exist: {self.script_path}"
            
        if not os.path.isfile(self.script_path):
            return False, f"Path is not a file: {self.script_path}"
            
        # Get file extension
        ext = self.get_extension()
        
        if ext not in self.VALID_EXTENSIONS:
            valid_exts = ', '.join(self.VALID_EXTENSIONS.keys())
            return False, f"Invalid script file type '{ext}'. Valid types: {valid_exts}"
            
        return True, "Valid script file"
    
    def execute_script(self) -> bool:
        """Execute the user-defined script"""
        # Validate script file first
        is_valid, error_msg = self.is_valid_script_file()
        if not is_valid:
            print(f"Script validation failed: {error_msg}")
            return False

        try:
            # Auto-detect script type from file extension if not explicitly set
            ext = self.get_extension()
            detected_type = self.VALID_EXTENSIONS.get(ext)
            
            # Build command based on script type
            if detected_type == "python":
                cmd = ["python", self.script_path]
            elif detected_type == "batch":
                cmd = [self.script_path]
            elif detected_type == "powershell":
                cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", self.script_path]
            elif detected_type == "bash":
                cmd = ["bash", self.script_path]
            else:
                # Generic execution
                cmd = [self.script_path]
            
            print(f"Executing script: {' '.join(cmd)}")
            
            # Execute the script
            result = subprocess.run(
                cmd,
                cwd=self.working_directory,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout
            )
            
            if result.returncode == 0:
                print("Script executed successfully.")
                if result.stdout:
                    print(f"Script output: {result.stdout}")
                return True
            else:
                print(f"Script execution failed with return code {result.returncode}")
                if result.stderr:
                    print(f"Script error: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print(f"Script execution timed out after {self.timeout} seconds")
            return False
        except Exception as e:
            print(f"Error executing script: {e}")
            return False
