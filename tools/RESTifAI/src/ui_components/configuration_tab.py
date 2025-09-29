import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
from src.script_executor import ScriptExecutor
from config import Paths

class ConfigurationTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.create_ui()

    def create_ui(self):
        """Create the configuration UI"""
        # Main container with padding
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Title
        title_label = ttk.Label(main_frame, text="Configuration Settings", 
                               font=('Segoe UI', 16, 'bold'))
        title_label.pack(anchor="w", pady=(0, 20))

        # API Configuration Section
        api_frame = ttk.LabelFrame(main_frame, text="API Configuration", padding=15)
        api_frame.pack(fill="x", pady=(0, 20))
        
        # Configure grid column weights for proper expansion
        api_frame.grid_columnconfigure(1, weight=1)
        
        # Base URL field
        ttk.Label(api_frame, text="Base URL:").grid(row=0, column=0, sticky="w", pady=5)
        base_url_entry = ttk.Entry(api_frame, textvariable=self.app.base_url_var, width=50)
        base_url_entry.grid(row=0, column=1, sticky="w", padx=(10, 0), pady=5)
        
        # Test Connection button
        test_api_btn = ttk.Button(api_frame, text="Test API Connection", 
                                 command=self.test_api_connection)
        test_api_btn.grid(row=1, column=0, columnspan=2, pady=(10, 0), sticky="w")        # LLM Configuration Section
        llm_frame = ttk.LabelFrame(main_frame, text="LLM Configuration", padding=15)
        llm_frame.pack(fill="x", pady=(0, 20))

        # LLM Test Connection and Info Buttons
        llm_button_frame = ttk.Frame(llm_frame)
        llm_button_frame.pack(fill="x", pady=(0, 0))
        
        test_llm_btn = ttk.Button(llm_button_frame, text="Test LLM Connection", 
                                 command=self.test_llm_connection)
        test_llm_btn.pack(side="left", padx=(0, 10))

        info_llm_btn = ttk.Button(llm_button_frame, text="ℹ Setup Info", 
                                 command=self.show_llm_setup_info)
        info_llm_btn.pack(side="left", padx=(0, 10))

        self.llm_status_label = ttk.Label(llm_button_frame, text="Not tested", 
                                         foreground="gray")
        self.llm_status_label.pack(side="left", padx=(10, 0))

        # LLM Context Information Section
        llm_context_frame = ttk.LabelFrame(main_frame, text="User information (optional)", padding=15)
        llm_context_frame.pack(fill="x", pady=(0, 20))
        
        # Configure grid column weights for proper expansion
        llm_context_frame.grid_columnconfigure(1, weight=1)
        
        # Create the LLM input field
        self.create_llm_context_field(llm_context_frame)

        # Environment Configuration Section
        env_init_frame = ttk.LabelFrame(main_frame, text="Environment Initialization Configuration (optional)", padding=15)
        env_init_frame.pack(fill="both", expand=True, pady=(0, 20))

        # Environment initialization checkbox with info button in a frame
        reset_checkbox_frame = ttk.Frame(env_init_frame)
        reset_checkbox_frame.pack(fill="x", pady=(0, 10))
        
        use_env_init_cb = ttk.Checkbutton(reset_checkbox_frame, text="Enable", 
                                         variable=self.app.use_environment_initialization_var,
                                         command=self.toggle_env_init_fields)
        use_env_init_cb.pack(side="left")
        
        info_env_init_btn = ttk.Button(reset_checkbox_frame, text="ℹ Info", 
                                      command=self.show_script_info)
        info_env_init_btn.pack(side="left", padx=(5, 0))

        # Script Configuration
        self.create_script_config(env_init_frame)

        # Execute Script Button
        test_frame = ttk.Frame(env_init_frame)
        test_frame.pack(fill="x", pady=(20, 0))
        
        execute_script_btn = ttk.Button(test_frame, text="Execute Script", 
                                command=self.execute_script)
        execute_script_btn.pack(side="left")

        connection_status_frame = ttk.Frame(test_frame)
        connection_status_frame.pack(side="right", fill="x", expand=True)
        
        self.connection_status_label = ttk.Label(connection_status_frame, text="Not executed", 
                                                foreground="gray")
        self.connection_status_label.pack(side="right")

        # Initialize field states and environment initializer
        self.toggle_env_init_fields()

    def test_api_connection(self):
        """Test the API connection with current settings"""
        try:
            import requests
            
            base_url = self.app.base_url_var.get().strip()
            if not base_url:
                messagebox.showerror("Error", "Please enter a base URL")
                return
            
            # Test connection
            response = requests.get(base_url, timeout=10)
            
            if response.status_code < 400:
                messagebox.showinfo(
                    "Connection Successful", 
                    f"Successfully connected to {base_url}\n"
                    f"Status Code: {response.status_code}"
                )
            else:
                messagebox.showwarning(
                    "Connection Warning",
                    f"Connected but received status code: {response.status_code}"
                )
                
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Connection Error", f"Failed to connect to {base_url}\n\nError: {str(e)}")
        except Exception as e:
            messagebox.showerror("Error", f"Unexpected error: {str(e)}")

    def create_script_config(self, parent_frame):
        """Create Script configuration form"""
        # Script configuration frame - using a plain Frame
        script_frame = ttk.Frame(parent_frame)
        script_frame.pack(fill="x", pady=(10, 0))
        
        # Script path label
        script_info_frame = ttk.Frame(script_frame)
        script_info_frame.grid(row=0, column=0, columnspan=4, sticky="ew", pady=5, padx=(10, 5))
        
        ttk.Label(script_info_frame, text="Reset Script Path:").pack(side="left")
        
        script_path_frame = ttk.Frame(script_frame)
        script_path_frame.grid(row=1, column=0, columnspan=4, sticky="ew", pady=5, padx=(5, 10))
        script_path_frame.grid_columnconfigure(0, weight=1)

        self.script_path_var = tk.StringVar()
        self.script_path_entry = ttk.Entry(script_path_frame, textvariable=self.script_path_var, width=50)
        self.script_path_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.script_path_entry.bind('<KeyRelease>', lambda e: self.update_environment_initializer())

        browse_script_btn = ttk.Button(script_path_frame, text="Browse", 
                                      command=self.browse_script_file)
        browse_script_btn.grid(row=0, column=1)

        # Configure grid weights
        script_frame.grid_columnconfigure(1, weight=1)

    def create_llm_context_field(self, parent_frame):
        """Create LLM context field for basecase test generation guidance"""
        # LLM Context section label
        llm_context_label = ttk.Label(parent_frame, text="Basecase Test Generation Context:", 
                                     font=("Segoe UI", 10, "bold"))
        llm_context_label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))
        
        # LLM Context text area label
        llm_context_text_label = ttk.Label(parent_frame, text="Context for LLM:")
        llm_context_text_label.grid(row=1, column=0, sticky="nw", pady=2)
        
        # Create a frame for the text widget and scrollbar
        text_frame = ttk.Frame(parent_frame)
        text_frame.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=2)
        text_frame.grid_columnconfigure(0, weight=1)
        
        # Text widget for multi-line input
        self.user_input_text = tk.Text(text_frame, height=4, width=50, wrap=tk.WORD)
        self.user_input_text.grid(row=0, column=0, sticky="ew")
        
        # Scrollbar for text widget
        user_input_scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.user_input_text.yview)
        user_input_scrollbar.grid(row=0, column=1, sticky="ns")
        self.user_input_text.configure(yscrollcommand=user_input_scrollbar.set)
        
        # Bind text change event to update the app variable
        self.user_input_text.bind('<KeyRelease>', self.on_user_input_change)
        self.user_input_text.bind('<Button-1>', self.on_user_input_change)
        
        # Help text for LLM context
        llm_context_help = ttk.Label(
            parent_frame,
            text="This information is directly provided to the LLM for generating the happy path.\nSpecify values and details not available in the OpenAPI specification (e.g., valid IDs, auth tokens, required parameters).",
            font=("Segoe UI", 8),
            foreground="#666666",
            justify="left"
        )
        llm_context_help.grid(row=2, column=0, columnspan=2, sticky="w", pady=(5, 0))

    def on_user_input_change(self, event=None):
        """Update the app's user input variable when text changes"""
        content = self.user_input_text.get("1.0", tk.END).strip()
        self.app.user_input_var.set(content)

    def toggle_env_init_fields(self):
        """Enable/disable environment initialization fields based on checkbox"""
        state = "normal" if self.app.use_environment_initialization_var.get() else "disabled"
        
        # Script fields
        if hasattr(self, 'script_path_entry'):
            self.script_path_entry.config(state=state)
        
        self.update_environment_initializer()

    def update_environment_initializer(self):
        """Create or update the environment initializer with current configuration"""
        if not self.app.use_environment_initialization_var.get():
            self.app.environment_initializer = None
            self.app.update_status("Environment initialization disabled")
            self.connection_status_label.config(text="Disabled", foreground="gray")
            return

        try:
            self.app.environment_initializer = ScriptExecutor(self.script_path_var.get())
            self.app.update_status("Environment initializer configured")
            self.connection_status_label.config(text="Script configured", foreground="green")
                    
        except Exception as e:
            print(f"Warning: Could not create environment initializer: {e}")
            self.app.environment_initializer = None
            self.connection_status_label.config(text="Configuration error", foreground="red")

    def browse_script_file(self):
        """Browse for script file"""
        file_types = [
            ("All files", "*.*"),
            ("PowerShell files", "*.ps1"),
            ("Python files", "*.py"),
            ("Batch files", "*.bat"),
            ("Shell scripts", "*.sh")
        ]
        
        # Set initial directory to environment initialization scripts folder
        initial_dir = Paths.get_env_init_scripts()
        
        filename = filedialog.askopenfilename(
            title="Select Script File", 
            filetypes=file_types,
            initialdir=initial_dir
        )
        if filename:
            # Validate the selected file using ScriptExecutor validation
            try:
                temp_executor = ScriptExecutor(filename)
                is_valid, error_msg = temp_executor.is_valid_script_file()
                
                if not is_valid:
                    messagebox.showerror("Invalid Script File", 
                                       f"{error_msg}")
                    return
                    
                self.script_path_var.set(filename)
                self.update_environment_initializer()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to validate script file:\n{str(e)}")
                return

    def execute_script(self):
        """Execute the environment initialization script"""
        if not self.app.use_environment_initialization_var.get():
            messagebox.showinfo("Info", "Environment initialization is disabled")
            return

        if not self.app.environment_initializer:
            messagebox.showerror("Error", "No environment initializer configured")
            return

        try:
            success = self.app.environment_initializer.execute_script()
            
            if success:
                messagebox.showinfo("Success", "Script executed successfully!")
                self.app.update_status("Environment initialization script executed successfully")
                self.connection_status_label.config(text="Executed", foreground="green")
            else:
                messagebox.showerror("Execution Failed", "Script execution failed")
                self.app.update_status("Environment initialization script execution failed")
                self.connection_status_label.config(text="Failed", foreground="red")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to execute script:\n{str(e)}")
            self.app.update_status("Environment initialization script execution failed")
            self.connection_status_label.config(text="Error", foreground="red")

    def test_llm_connection(self):
        """Test the LLM connection using environment variables"""
        try:
            from llm_manager import LLMManager
            
            # Try to create LLM manager with environment variables
            llm_manager = LLMManager()  # Uses environment variables by default
            
            if llm_manager.is_running():
                messagebox.showinfo("Success", "LLM connection successful!")
                self.app.update_status("LLM connection tested successfully")
                self.llm_status_label.config(text="Connected", foreground="green")
                # Store the working LLM manager in the app
                self.app.llm_manager = llm_manager
                # Update header status
                self.app.refresh_llm_status()
            else:
                messagebox.showerror("Connection Failed", "LLM connection failed")
                self.app.update_status("LLM connection test failed")
                self.llm_status_label.config(text="Failed", foreground="red")
                self.app.llm_manager = None
                self.app.refresh_llm_status()
            
        except ValueError as e:
            # This handles missing environment variables
            messagebox.showerror("Configuration Error", 
                               f"LLM configuration error:\n{str(e)}\n\n"
                               "Click 'Setup Info' for guidance on setting environment variables.")
            self.llm_status_label.config(text="Not configured", foreground="red")
            self.app.llm_manager = None
            self.app.refresh_llm_status()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to test LLM connection:\n{str(e)}")
            self.llm_status_label.config(text="Error", foreground="red")
            self.app.llm_manager = None
            self.app.refresh_llm_status()

    def show_llm_setup_info(self):
        """Show information about setting up LLM environment variables"""
        info_message = """LLM Environment Variables Setup

To configure the LLM connection, create a .env file in the project folder with these variables:

# OpenAI Configuration
OPENAI_API_KEY="your_api_key_here"
OPENAI_MODEL_NAME="gpt-4.1-mini"

# Or Azure OpenAI Configuration
AZURE_OPENAI_API_KEY="your_api_key_here"
AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
AZURE_OPENAI_DEPLOYMENT="gpt-4.1-mini"
AZURE_OPENAI_API_VERSION="2025-01-01-preview"

Important: Restart your IDE or Computer after setting system environment variables for them to take effect."""

        # Create custom dialog for better width control
        dialog = tk.Toplevel(self)
        dialog.title("LLM Setup Information")
        dialog.geometry("700x600")  # Make it wider
        dialog.resizable(True, True)
        dialog.transient(self)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (700 // 2)
        y = (dialog.winfo_screenheight() // 2) - (600 // 2)
        dialog.geometry(f"700x600+{x}+{y}")
        
        # Create main frame with padding
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Create text widget with scrollbar
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill="both", expand=True)
        
        text_widget = tk.Text(text_frame, wrap="word", font=("Consolas", 10), 
                             padx=10, pady=10, height=25, width=80)
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        text_widget.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Insert the message
        text_widget.insert("1.0", info_message)
        text_widget.config(state="disabled")  # Make it read-only
        
        # Add close button
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=(10, 0))
        
        close_btn = ttk.Button(button_frame, text="Close", command=dialog.destroy)
        close_btn.pack(side="right")

    def show_script_info(self):
        """Show information about when the script is executed"""
        info_message = """Environment Initialization Script Execution

The selected script will be executed automatically to ensure consistent test preconditions:

• Before each individual test case execution
• During happy path generation to establish baseline conditions

This ensures that every test starts with the same environment state, providing:
✓ Consistent and reproducible test results
✓ Isolated test execution (no interference between tests)
✓ Reliable baseline conditions for test generation

The script should initialize your environment to a known clean state"""

        # Create info dialog
        dialog = tk.Toplevel(self)
        dialog.title("Environment Initialization Script Information")
        dialog.geometry("600x400")
        dialog.resizable(True, True)
        dialog.transient(self)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (600 // 2)
        y = (dialog.winfo_screenheight() // 2) - (400 // 2)
        dialog.geometry(f"600x400+{x}+{y}")
        
        # Create main frame with padding
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Create text widget with scrollbar
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill="both", expand=True)
        
        text_widget = tk.Text(text_frame, wrap="word", font=("Segoe UI", 10), 
                             padx=10, pady=10, height=20, width=70)
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        text_widget.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Insert the message
        text_widget.insert("1.0", info_message)
        text_widget.config(state="disabled")  # Make it read-only
        
        # Add close button
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=(10, 0))
        
        close_btn = ttk.Button(button_frame, text="Close", command=dialog.destroy)
        close_btn.pack(side="right")