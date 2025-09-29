import tkinter as tk
from tkinter import ttk, messagebox
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import Paths, MAX_WORKERS
from basecase_flow_generator import BaselineFlowGenerator
from test_case_generator import TestCaseGenerator
from operation_flow import OperationFlowResult

class GenerationTap(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.create_ui()

    def create_ui(self):
        """Create the endpoint selection UI"""
        # Main container with padding
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Title
        title_label = ttk.Label(main_frame, text="Test Generation", 
                               font=('Segoe UI', 16, 'bold'))
        title_label.pack(anchor="w", pady=(0, 20))

        # Create paned window for layout
        paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned.pack(fill="both", expand=True)

        # Left panel - Endpoint selection
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        # Endpoint list
        endpoint_frame = ttk.LabelFrame(left_frame, text="Available Endpoints", padding=10)
        endpoint_frame.pack(fill="both", expand=True, pady=(0, 10))

        # Endpoint listbox with scrollbar
        list_frame = ttk.Frame(endpoint_frame)
        list_frame.pack(fill="both", expand=True)

        self.endpoint_listbox = tk.Listbox(list_frame, selectmode=tk.MULTIPLE, font=('Consolas', 10))
        endpoint_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.endpoint_listbox.yview)
        self.endpoint_listbox.configure(yscrollcommand=endpoint_scrollbar.set)

        self.endpoint_listbox.pack(side="left", fill="both", expand=True)
        endpoint_scrollbar.pack(side="right", fill="y")

        # Endpoint selection buttons
        selection_frame = ttk.Frame(left_frame)
        selection_frame.pack(fill="x", pady=10)

        select_all_btn = ttk.Button(selection_frame, text="Select All", 
                                   command=self.select_all_endpoints)
        select_all_btn.pack(side="left", padx=(0, 5))

        clear_selection_btn = ttk.Button(selection_frame, text="Clear Selection", 
                                        command=self.clear_endpoint_selection)
        clear_selection_btn.pack(side="left", padx=5)
        
        # Test generation controls
        generation_frame = ttk.LabelFrame(left_frame, text="Test Generation", padding=10)
        generation_frame.pack(fill="x")
          # Test case type selection
        test_type_frame = ttk.Frame(generation_frame)
        test_type_frame.pack(fill="x", pady=(0, 10))

        # Header with info button
        header_frame = ttk.Frame(test_type_frame)
        header_frame.pack(fill="x")
        
        ttk.Label(header_frame, text="Test Types:", font=('Segoe UI', 10, 'bold')).pack(side="left")
        
        info_btn = ttk.Button(header_frame, text="Info", width=8,
                             command=self.show_test_generation_info)
        info_btn.pack(side="right")
        
        # Create a frame for the two buttons side by side
        buttons_frame = ttk.Frame(test_type_frame)
        buttons_frame.pack(fill="x", pady=(10, 0))
        
        self.use_structural_var = tk.BooleanVar(value=True)
        structural_button = ttk.Checkbutton(buttons_frame, 
                                          text="Structural", 
                                          variable=self.use_structural_var)
        structural_button.pack(side="left", padx=(0, 20))
        
        self.use_functional_var = tk.BooleanVar(value=True)
        functional_button = ttk.Checkbutton(buttons_frame, 
                                          text="Functional",
                                          variable=self.use_functional_var)
        functional_button.pack(side="left")
        
        # Add tooltip labels to explain the test types
        ttk.Label(test_type_frame, 
                 text="   Structural: Tests API specification violations (missing fields, invalid types, etc.)",
                 font=("Segoe UI", 8), foreground="gray").pack(anchor="w", pady=(5, 0))
        ttk.Label(test_type_frame, 
                 text="   Functional: Tests business logic violations (semantic errors, state transitions, etc.)",
                 font=("Segoe UI", 8), foreground="gray").pack(anchor="w", pady=(2, 0))

        generate_btn = ttk.Button(generation_frame, text="Generate AI Tests", 
                                 command=self.start_test_generation)
        generate_btn.pack(fill="x", pady=(10, 0))

        # Right panel - Output and progress
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=2)

        # Output section
        output_frame = ttk.LabelFrame(right_frame, text="Generation Output", padding=10)
        output_frame.pack(fill="both", expand=True)

        # Output text with scrollbar
        output_text_frame = ttk.Frame(output_frame)
        output_text_frame.pack(fill="both", expand=True)

        self.output_text = tk.Text(output_text_frame, wrap="word", font=('Consolas', 9))
        output_scrollbar = ttk.Scrollbar(output_text_frame, orient="vertical", command=self.output_text.yview)
        self.output_text.configure(yscrollcommand=output_scrollbar.set)

        self.output_text.pack(side="left", fill="both", expand=True)
        output_scrollbar.pack(side="right", fill="y")

        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(right_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill="x", pady=(10, 0))

        # Status label
        self.process_status_label = ttk.Label(right_frame, text="Ready to generate tests")
        self.process_status_label.pack(anchor="w", pady=(5, 0))

        # Load endpoints if available
        self.refresh_endpoints()

    def refresh_endpoints(self):
        """Refresh the endpoint list"""
        self.endpoint_listbox.delete(0, tk.END)
        
        if not self.app.endpoints:
            self.log("No endpoints loaded. Please load a specification first.")
            return

        for endpoint in self.app.endpoints:
            display_text = f"{endpoint.method.upper()} {endpoint.path} ({endpoint.operation_id})"
            self.endpoint_listbox.insert(tk.END, display_text)

        self.log(f"Loaded {len(self.app.endpoints)} endpoints")

    def select_all_endpoints(self):
        """Select all endpoints"""
        self.endpoint_listbox.select_set(0, tk.END)

    def clear_endpoint_selection(self):
        """Clear endpoint selection"""
        self.endpoint_listbox.selection_clear(0, tk.END)

    def start_test_generation(self):
        """Start test generation in a separate thread"""
        selected_indices = self.endpoint_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Warning", "Please select at least one endpoint")
            return

        # Check LLM connection at the moment of generation
        if not self.app.llm_manager:
            messagebox.showerror("LLM Connection Required", 
                               "No LLM connection available.\n\n"
                               "Test generation requires a working LLM connection. "
                               "Please ensure your LLM is properly configured and connected.")
            return
        
        # Test LLM connection right now
        try:
            if not self.app.llm_manager.is_running():
                messagebox.showerror("LLM Connection Failed", 
                                   "Unable to connect to LLM service.\n\n"
                                   "Test generation requires an active LLM connection. "
                                   "Please check your LLM service status and try again.")
                return
        except Exception as e:
            messagebox.showerror("LLM Connection Error", 
                               f"LLM connection error: {str(e)}\n\n"
                               "Unable to establish connection to LLM service. "
                               "Please verify your LLM service is running and accessible.")
            return

        # Get selected endpoints
        self.app.selected_endpoints = [self.app.endpoints[i] for i in selected_indices]
        
        self.log(f"Starting test generation for {len(self.app.selected_endpoints)} endpoints...")
        self.update_summary_log()

        # Start generation in background thread
        thread = threading.Thread(target=self.generate_tests_thread)
        thread.daemon = True
        thread.start()

    def generate_tests_thread(self):
        """Generate tests in background thread with parallel operation selection"""
        try:
            # Get user input from app
            user_input = self.app.get_user_input()
            
            self.app.baseline_generator = BaselineFlowGenerator(
                base_url=self.app.base_url_var.get(),
                endpoints=self.app.endpoints,
                llm_manager=self.app.llm_manager,
                user_input=user_input
            )

            self.app.test_case_generator = TestCaseGenerator(
                base_url=self.app.base_url_var.get(),
                endpoints=self.app.endpoints,
                llm_manager=self.app.llm_manager,
                spec_name=self.app.spec_name
            )

            # Log the user input being used
            if user_input:
                self.log(f"Using user input for context: {user_input[:100]}{'...' if len(user_input) > 100 else ''}")

            total_endpoints = len(self.app.selected_endpoints)
            
            self.update_progress(0, total_endpoints, "Selecting dependent operations in parallel...")
            
            max_workers = min(MAX_WORKERS, total_endpoints)
            completed_selections = 0
            
            # Identify dependent operations for each endpoint in parallel
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_endpoint = {
                    executor.submit(self.select_operations_for_endpoint, endpoint): endpoint 
                    for endpoint in self.app.selected_endpoints
                }
                
                for future in as_completed(future_to_endpoint):
                    endpoint = future_to_endpoint[future]
                    completed_selections += 1
                    
                    try:
                        success = future.result()
                        if success:
                            self.log(f"Operations selected for {endpoint.operation_id}: {endpoint.dependent_operations}")
                        else:
                            self.log(f"Failed to select operations for {endpoint.operation_id}")
                    except Exception as e:
                        self.log(f"Error selecting operations for {endpoint.operation_id}: {str(e)}")
                    
                    progress = (completed_selections / total_endpoints) * 50
                    self.update_progress(
                        completed_selections, 
                        total_endpoints, 
                        f"Selected operations for {completed_selections}/{total_endpoints} endpoints"
                    )
            
            self.log("All dependent operation selections finished")
            
            # Process each endpoint sequentially for independent test generation
            self.log("Processing endpoints with selected operations...")
            successes = 0
            failures = 0
            server_errors = 0
            
            for i, endpoint in enumerate(self.app.selected_endpoints):
                try:
                    operation_id = endpoint.operation_id
                    
                    progress = 50 + (i / total_endpoints) * 50
                    self.update_progress(
                        i, 
                        total_endpoints, 
                        f"Phase 2: Processing {operation_id}... ({i+1}/{total_endpoints})"
                    )
                    
                    self.log(f"\n{'='*60}")
                    self.log(f"Processing endpoint: {endpoint.method.upper()} {endpoint.path}")
                    self.log(f"Operation ID: {operation_id}")
                    
                    if not endpoint.dependent_operations:
                        self.log(f"No selected operations available for {operation_id}. Skipping...")
                        failures += 1
                        continue
                    
                    self.log(f"Using pre-selected operations: {endpoint.dependent_operations}")
                    
                    if self.app.environment_initializer and self.app.use_environment_initialization_var.get():
                        self.log("Initializing environment...")
                        reset_success = self.app.environment_initializer.execute_script()
                        if reset_success:
                            self.log("Environment initialization completed successfully")
                        else:
                            self.log("Environment initialization failed")
                    
                    self.log("Generating Happy Path...")
                    valid_operation_flow = self.app.baseline_generator.generate_valid_operation_flow(
                        operation_id, endpoint.dependent_operations, endpoint.usage_guide
                    )
                    
                    if valid_operation_flow.result == OperationFlowResult.SERVER_ERROR:
                        self.log(f"Server error for operation {operation_id} while Happy Path generation. Skipping negative test generation...")
                        server_errors += 1
                        continue

                    if valid_operation_flow.result == OperationFlowResult.FAILURE:
                        self.log(f"Generation of Happy Path for {operation_id} failed. Skipping negative test generation...")
                        failures += 1
                        continue
                    
                    successes += 1
                    self.log("Happy Path generated successfully")
                    self.log(f"Flow result: {valid_operation_flow.previous_values_to_string()}")
                    
                    use_structural = self.use_structural_var.get()
                    use_functional = self.use_functional_var.get()
                    
                    if not use_structural and not use_functional:
                        self.log("No negative test types selected. Generating only valid basecase test.")
                        test_descriptions = []
                    else:
                        test_type_msg = []
                        if use_structural:
                            test_type_msg.append("structural")
                        if use_functional:
                            test_type_msg.append("functional")
                            
                        self.log(f"Generating negative test case scenarios ({', '.join(test_type_msg)})...")
                            
                        test_descriptions = self.app.test_case_generator.generate_negative_test_case_descriptions(
                            valid_operation_flow,
                            use_structural=use_structural,
                            use_functional=use_functional
                        )
                        
                        self.log(f"Generated {len(test_descriptions)} test case scenarios:")
                        for test in test_descriptions:
                            self.log(f"  - {test.test_name}: {test.description}")
                    
                    if test_descriptions:
                        self.log("Generating negative test case values...")
                    else:
                        self.log("Generating valid test case...")
                    
                    test_suite_name = f"Test{operation_id.capitalize()}"
                    self.app.test_case_generator.generate_test_suite(
                        valid_operation_flow=valid_operation_flow, 
                        test_suite_name=test_suite_name,                        
                        test_case_descriptions=test_descriptions,
                    )
                    
                    if test_descriptions:
                        self.log(f"Test suite '{test_suite_name}' generated successfully!")
                        tests_dir = Paths.get_tests()
                        self.log(f"Individual test case collections created in '{tests_dir / test_suite_name}'")
                        self.log(f"Total collections: {len(test_descriptions) + 1} (1 valid + {len(test_descriptions)} negative)")
                    else:
                        self.log(f"Valid test case '{test_suite_name}' generated successfully!")
                        tests_dir = Paths.get_tests()
                        self.log(f"Test case collection created in '{tests_dir / test_suite_name}'")
                        self.log(f"Total collections: 1 (valid basecase only)")
                        
                except Exception as e:
                    self.log(f"Error processing {endpoint.operation_id}: {str(e)}")
                    failures += 1
                    
            self.update_progress(total_endpoints, total_endpoints, "Test generation completed!")
            self.log(f"\n{'='*60}")
            self.log("Test generation completed!")
            self.log(f"Summary: {successes} successes, {server_errors} server errors, {failures} failures")
            
            test_types = []
            if self.use_structural_var.get():
                test_types.append("structural")
            if self.use_functional_var.get():
                test_types.append("functional")
            
            if test_types:
                test_type_str = f"valid basecase + {', '.join(test_types)} negative tests"
            else:
                test_type_str = "valid basecase tests only"
                
            self.log(f"Test generation type: {test_type_str}")
            
            self.log("Check the Test Reports tab to view results.")
            self.log(f"Generated Postman collections are saved in the current run folder: {Paths.get_current_run_folder()}.")

            self.log(f"Cost of LLM usage: ${format(self.app.llm_manager.get_total_cost(), '.6f')} USD")
            self.log(f"Total tokens used: {self.app.llm_manager.get_total_tokens()}")

        except Exception as e:
            self.log(f"Error during test generation: {str(e)}")
            self.update_progress(0, 100, "Error occurred")
    
    def select_operations_for_endpoint(self, endpoint):
        """Select operations for a single endpoint - runs in parallel"""
        try:
            operation_id = endpoint.operation_id
            self.log(f"[Worker {threading.current_thread().name}] Selecting operations for {operation_id}...")
            
            selected_operations, usage_guide = self.app.baseline_generator.select_operations(operation_id)
            
            endpoint.dependent_operations = selected_operations
            endpoint.usage_guide = usage_guide
            
            return True
            
        except Exception as e:
            self.log(f"Error selecting operations for {endpoint.operation_id}: {str(e)}")
            return False

    def update_progress(self, current, total, status):
        """Update progress bar and status"""
        def update():
            progress = (current / total) * 100 if total > 0 else 0
            self.progress_var.set(progress)
            self.process_status_label.config(text=status)
            self.app.update_status(status)
        
        self.after(0, update)

    def log(self, message):
        """Add message to output text"""
        def add_log():
            self.output_text.insert(tk.END, message + "\n")
            self.output_text.see(tk.END)
        
        self.after(0, add_log)
    
    def update_summary_log(self):
        """Update the summary log with selected test options"""
        test_types = []
        if self.use_structural_var.get():
            test_types.append("structural")
        if self.use_functional_var.get():
            test_types.append("functional")
            
        if test_types:
            test_type_str = ", ".join(test_types)
            self.log(f"Selected test types: valid basecase + {test_type_str}")
        else:
            self.log("Selected test types: valid basecase only (no negative tests selected)")
        
        self.log("Valid basecase tests will always be generated")

    def show_test_generation_info(self):
        """Show information about how test cases are generated"""
        from tkinter import messagebox
        
        info_text = """How Test Cases Are Generated:

Valid Basecase Tests (Always Generated):
• First, a valid request is sent to the selected endpoint
• If successful, this proves the endpoint works correctly
• Creates a baseline for comparison with negative tests

Structural Negative Tests:
• Based on the OpenAPI specification
• Tests missing required fields, invalid data types, wrong formats
• Examples: missing parameters, invalid email formats, wrong number ranges

Functional Negative Tests:
• Based on business logic and domain rules
• Tests semantic violations and invalid state transitions
• Examples: setting end date before start date, accessing unauthorized resources

Test Generation Process:
1. Send valid request (Happy Path) that results in 2xx success
2. Generate invalid test scenarios that should result in 4xx client errors based on selected test types
3. Generate negative parameter values for each scenario and substitute into happy path values
4. Create Postman collections for valid and negative tests
5. Each test verifies the server properly validates and rejects invalid input

The goal is to ensure your API handles both valid and invalid requests correctly!"""
        
        messagebox.showinfo("Test Generation Information", info_text)