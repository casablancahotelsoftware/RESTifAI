import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import tkinter as tk
from tkinter import ttk
import os

# Import component classes
from ui_components.configuration_tab import ConfigurationTab
from ui_components.specification_tab import SpecificationTab
from ui_components.report_tab import TestReportsTab
from ui_components.generation_tab import GenerationTap
from ui_components.tests_tab import TestsTab

from llm_manager import LLMManager

class TestGeneratorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RESTifAI")
        self.geometry("1400x900")
        self.minsize(1200, 800)

        # Initialize modern styling
        self.style = ttk.Style(self)
        self.configure_modern_theme()

        # Configure main window background
        self.configure(bg="#f8fafc")

        # Initialize shared data
        self.init_shared_data()
        
        # Create the main UI with navigation
        self.create_main_ui()

    def init_shared_data(self):
        """Initialize shared data that components will access"""
        # Variables for user inputs
        self.base_url_var = tk.StringVar(value="https://petstore.swagger.io/v2")
        self.use_environment_initialization_var = tk.BooleanVar(value=False)
        self.spec_file_var = tk.StringVar()

        # User input variable
        self.user_input_var = tk.StringVar()
        
        self.spec = None
        self.parser = None
        self.endpoints = []
        self.selected_endpoints = []
        self.baseline_generator = None
        self.test_case_generator = None
        self.environment_initializer = None
        
        # Initialize LLM manager on startup
        self.llm_manager = None
        self.init_llm_manager()

        # Processing state
        self.current_endpoint_index = 0
        self.current_endpoint = None
        self.selected_operations = []
        self.valid_operation_flow = None
        self.test_descriptions = []

    def get_user_input(self):
        """Get the user input as a string or None"""
        user_input = self.user_input_var.get().strip()
        return user_input if user_input else None

    @property
    def spec_name(self):
        """Get specification name based on loaded specification file"""
        spec_file = self.spec_file_var.get()
        if spec_file:
            from pathlib import Path
            return Path(spec_file).stem  # Get filename without extension
        else:
            return "unknown_spec"

    def init_llm_manager(self):
        """Initialize LLM manager on startup without showing error messages"""
        try:
            self.llm_manager = LLMManager()
        except Exception:
            self.llm_manager = None

    def create_main_ui(self):
        """Create the main UI with navigation tabs"""
        # Create header frame with title and connection status
        header_frame = ttk.Frame(self)
        header_frame.pack(fill="x", padx=10, pady=(10, 0))
        
        # App title on the left
        title_label = ttk.Label(header_frame, text="RESTifAI", 
                               font=('Segoe UI', 14, 'bold'))
        title_label.pack(side="left")

        # LLM connection status 
        self.llm_status_frame = ttk.Frame(header_frame)
        self.llm_status_frame.pack(side="right", padx=(0, 20))
        
        self.llm_status_label = ttk.Label(self.llm_status_frame, text="LLM: Disconnected", 
                                         font=('Segoe UI', 10))
        self.llm_status_label.pack(side="right", padx=(0, 5))
        
        self.llm_status_icon = ttk.Label(self.llm_status_frame, text="●", 
                                        font=('Segoe UI', 12), 
                                        foreground="red")
        self.llm_status_icon.pack(side="right")
        
        # Bind click event to status indicator for manual refresh
        self.llm_status_icon.bind("<Button-1>", lambda e: self.refresh_llm_status())
        self.llm_status_label.bind("<Button-1>", lambda e: self.refresh_llm_status())
        
        # Create status bar first (before components that might use it)
        self.status_bar = ttk.Frame(self)
        self.status_bar.pack(fill="x", side="bottom", padx=10, pady=(0, 10))
        
        self.status_label = ttk.Label(self.status_bar, text="Ready")
        self.status_label.pack(side="left")

        # Create the main navigation notebook
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Add tab change event to automatically refresh content
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        # Create component tabs (now that status_label exists)
        self.configuration_tab = ConfigurationTab(self.notebook, self)
        self.specification_tab = SpecificationTab(self.notebook, self)
        self.endpoint_selection_tab = GenerationTap(self.notebook, self)
        self.tests_tab = TestsTab(self.notebook, self)
        self.test_reports_tab = TestReportsTab(self.notebook, self)

        # Add tabs to notebook
        self.notebook.add(self.configuration_tab, text="Configuration")
        self.notebook.add(self.specification_tab, text="Specification")
        self.notebook.add(self.endpoint_selection_tab, text="Test Generation")
        self.notebook.add(self.tests_tab, text="Test Overview and Execution")
        self.notebook.add(self.test_reports_tab, text="Test Reports")
        
        # Initialize LLM status
        self.refresh_llm_status()

    def configure_modern_theme(self):
        """Configure a modern theme with gradient background and updated colors."""
        self.style.theme_use('default')
        self.configure(bg="#f8fafc")
        self.style.configure('.', background="#f8fafc", foreground="#002f55", font=('Segoe UI', 11))
        self.style.configure('TLabel', background="#f8fafc", foreground="#002f55", font=('Segoe UI', 11))
        self.style.configure('TButton', background="#f1b400", foreground="#002f55", font=('Segoe UI', 11, 'bold'))
        self.style.map('TButton',
                       background=[('active', '#d9a000')],
                       foreground=[('active', '#002f55')])
        self.style.configure('TEntry', fieldbackground="#ffffff", foreground="#002f55", font=('Segoe UI', 11))
        self.style.configure('TFrame', background="#f8fafc")
        self.style.configure('TLabelFrame', background="#f8fafc", foreground="#002f55", font=('Segoe UI', 11))
        self.style.configure('TNotebook', background="#f8fafc")
        self.style.configure('TNotebook.Tab', padding=[20, 10])

    def update_status(self, message):
        """Update the status bar message"""
        self.status_label.config(text=message)

    def log(self, message):
        """Log a message to the output (will be called by components)"""
        # This will be handled by the appropriate tab that has output
        if hasattr(self, 'endpoint_selection_tab'):
            self.endpoint_selection_tab.log(message)

    def refresh_llm_status(self):
        """Refresh the LLM connection status indicator"""
        try:
            if self.llm_manager:
                # Test the LLM connection
                if self.llm_manager.is_running():
                    self.llm_status_icon.config(text="●", foreground="green")
                    self.llm_status_label.config(text="LLM: Connected")
                else:
                    self.llm_status_icon.config(text="●", foreground="red")
                    self.llm_status_label.config(text="LLM: Failed")
                    self.llm_manager = None
            else:
                self.llm_status_icon.config(text="●", foreground="red")
                self.llm_status_label.config(text="LLM: Not Configured")
        except Exception as e:
            self.llm_status_icon.config(text="●", foreground="red")
            self.llm_status_label.config(text="LLM: Error")
            self.llm_manager = None
            
    def on_tab_changed(self, event):
        """Handle tab change events to automatically refresh content"""
        selected_tab = self.notebook.index("current")
        
        # Refresh content based on selected tab
        if selected_tab == 2:  # Generate Tab
            if hasattr(self, 'endpoint_selection_tab'):
                self.endpoint_selection_tab.refresh_endpoints()
        elif selected_tab == 3:  # Tests Tab
            if hasattr(self, 'tests_tab'):
                self.tests_tab.refresh_run_list()
                self.tests_tab.load_test_suites()
        elif selected_tab == 4:  # Reports Tab
            if hasattr(self, 'test_reports_tab'):
                self.test_reports_tab.refresh_run_list()
                self.test_reports_tab.load_test_suites()

    # Navigation methods for components to switch tabs
    def switch_to_specification(self):
        """Switch to specification tab"""
        self.notebook.select(1)

    def switch_to_endpoints(self):
        """Switch to generate tab"""
        self.notebook.select(2)

    def switch_to_tests(self):
        """Switch to tests tab"""
        self.notebook.select(3)

    def switch_to_test_reports(self):
        """Switch to reports tab"""
        self.notebook.select(4)

    def start(self):
        self.mainloop()

if __name__ == "__main__":
    app = TestGeneratorApp()
    app.start()
