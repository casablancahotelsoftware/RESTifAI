"""
Configuration file for RESTifAI
Central location for all folder paths and directory configurations
"""
from pathlib import Path
from datetime import datetime
from typing import Tuple

# Maximum number of concurrent workers for dependent operation selection (token intensive)
# Limit this to avoid running into LLM rate limits (e.g. for OhSome service)
MAX_WORKERS = 10

MAX_VALID_REQUEST_VALUE_GENERATION_RETRIES = 10

MODEL_TEMPERATURE = 0.0  # Default temperature for LLM responses, can be adjusted per model
MODEL_TIMEOUT = 60 # Used to terminate hallucinations (undetermined LLM output generation)

PROJECT_ROOT = Path(__file__).parent.absolute()

class Paths:
    """Centralized path configuration for the RESTifAI application"""

    # Input directories
    SPECIFICATIONS = PROJECT_ROOT / "specifications"
    ENVIRONMENT_INIT_SCRIPTS = PROJECT_ROOT / "env_init_scripts"
    
    # Output directories  
    OUTPUT = PROJECT_ROOT / "output"
    TESTS = "tests"  # Subdirectory inside run folder
    REPORTS = "reports"  # Subdirectory inside run folder
    COMBINED_DATA = "combined_data"  # Subdirectory inside run folder
    FAILED_TESTCASE_VALUE_GENERATIONS = "failed_testcase_value_generations.json"
    
    # Current run directory
    _current_run = None

    #Used for MCP server only
    ENVIRONMENT_INIT_SCRIPT = ENVIRONMENT_INIT_SCRIPTS / "restart-petstore.ps1"

    @classmethod
    def ensure_directories_exist(cls):
        """Create all necessary directories if they don't exist"""
        directories = [
            cls.OUTPUT,
            cls.SPECIFICATIONS,
            cls.ENVIRONMENT_INIT_SCRIPTS,
        ]
        
        for directory in directories:
            directory.mkdir(exist_ok=True)
    
    @classmethod
    def get_run_folder_name(cls, spec_name):
        """Generate a run folder name using specification name and timestamp"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{spec_name}.{timestamp}"
    
    @classmethod
    def create_run_folder(cls, spec_name):
        """Create a new run folder and return its path"""
        run_folder_name = cls.get_run_folder_name(spec_name)
        cls.OUTPUT.mkdir(exist_ok=True)
        run_folder_path = cls.OUTPUT / run_folder_name
        run_folder_path.mkdir(exist_ok=True)
        
        # Create the subdirectories
        (run_folder_path / cls.TESTS).mkdir(exist_ok=True)
        (run_folder_path / cls.REPORTS).mkdir(exist_ok=True)
        (run_folder_path / cls.COMBINED_DATA).mkdir(exist_ok=True)
        
        cls._current_run = run_folder_path
        return run_folder_path
    
    @classmethod
    def get_current_run_folder(cls):
        """Get the current run folder or return None if none exists"""
        return cls._current_run
    
    @classmethod
    def set_current_run_folder(cls, run_folder_path):
        """Set the current run folder"""
        cls._current_run = Path(run_folder_path)
        return cls._current_run
    
    @classmethod
    def get_all_run_folders(cls):
        """Get all run folders in the output directory"""
        if not cls.OUTPUT.exists():
            return []
        
        return [
            folder for folder in cls.OUTPUT.iterdir() 
            if folder.is_dir() and not folder.name.startswith('.')
        ]
    
    # Path getters
    @classmethod
    def get_specifications(cls) -> Path:
        """Get specifications path as Path object"""
        return cls.SPECIFICATIONS
    
    @classmethod
    def get_output(cls) -> Path:
        """Get output path as Path object"""
        return cls.OUTPUT
    
    @classmethod
    def get_reports(cls) -> Path:
        """Get reports folder path for the current run as Path object"""
        run_folder = cls.get_current_run_folder()
        return (run_folder / cls.REPORTS) if run_folder else None
    
    @classmethod
    def get_tests(cls) -> Path:
        """Get tests folder path for the current run as Path object"""
        run_folder = cls.get_current_run_folder()
        return (run_folder / cls.TESTS) if run_folder else None
    
    @classmethod
    def get_combined_data(cls) -> Path:
        """Get combined data folder path for the current run as Path object"""
        run_folder = cls.get_current_run_folder()
        return (run_folder / cls.COMBINED_DATA) if run_folder else None
    
    @classmethod
    def get_env_init_scripts(cls) -> Path:
        """Get env_init_scripts path as Path object"""
        return cls.ENVIRONMENT_INIT_SCRIPTS
    
    @classmethod
    def get_env_init_script(cls) -> Path:
        """Get the path to the environment initialization script"""
        return cls.ENVIRONMENT_INIT_SCRIPT
    
    @classmethod
    def get_failed_testcase_value_generations_file(cls) -> Path:
        """Get path to the failed testcase value generations file for the current run"""
        run_folder = cls.get_current_run_folder()
        return (run_folder / cls.FAILED_TESTCASE_VALUE_GENERATIONS) if run_folder else None

Paths.ensure_directories_exist()
