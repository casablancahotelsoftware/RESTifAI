import os
import json
import shutil
import tkinter as tk
from tkinter import ttk, messagebox, Canvas

from config import Paths
from test_case_generator import TestCaseGenerator
from test_report_manager import TestReportManager

class CreateToolTip:
    """Create a tooltip for a given widget"""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.on_enter)
        self.widget.bind("<Leave>", self.on_leave)
        self.tooltip_window = None

    def on_enter(self, event=None):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25

        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        
        label = ttk.Label(self.tooltip_window, text=self.text, 
                         background="#ffffe0", relief="solid", borderwidth=1,
                         wraplength=180)
        label.pack()

    def on_leave(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

class TestReportsTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.current_test_suite = None
        self.current_test_case = None
        self.current_run_folder = None
        self.node_positions = {}
        self.node_width = 100
        self.node_height = 60
        self.node_spacing = 20
        self.create_ui()
        self.refresh_run_list()

    def create_ui(self):
        """Create the hierarchical test reports UI"""
        # Main container with padding
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Title
        title_label = ttk.Label(main_frame, text="Test Reports - Interactive Flow Visualization", 
                               font=('Segoe UI', 16, 'bold'))
        title_label.pack(anchor="w", pady=(0, 20))
        
        # Run selector section
        run_selector_frame = ttk.Frame(main_frame)
        run_selector_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Label(run_selector_frame, text="Select Run:").pack(side="left", padx=(0, 5))
        self.run_selector = ttk.Combobox(run_selector_frame, width=50, state="readonly")
        self.run_selector.pack(side="left", padx=(0, 10))
        self.run_selector.bind("<<ComboboxSelected>>", self.on_run_selected)
        
        # Add a delete run button
        self.delete_run_btn = ttk.Button(run_selector_frame, text="Delete Run", width=10,
                                        command=self.delete_current_run)
        self.delete_run_btn.pack(side="left")
        CreateToolTip(self.delete_run_btn, "Delete the currently selected run folder")

        # Controls section
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill="x", pady=(10, 15))

        back_btn = ttk.Button(controls_frame, text="Back to Suites", 
                             command=self.show_test_suites_view)
        back_btn.pack(side="left", padx=(0, 10))

        # Breadcrumb navigation
        self.breadcrumb_label = ttk.Label(main_frame, text="Test Suites", 
                                         font=('Segoe UI', 12, 'bold'))
        self.breadcrumb_label.pack(anchor="w", pady=(0, 10))

        # Create main content area with notebook
        self.main_notebook = ttk.Notebook(main_frame)
        self.main_notebook.pack(fill="both", expand=True)

        # Test Suites View
        self.suites_frame = ttk.Frame(self.main_notebook)
        self.main_notebook.add(self.suites_frame, text="Test Suites")
        
        self.create_suites_view()

        # Test Cases View  
        self.cases_frame = ttk.Frame(self.main_notebook)
        self.main_notebook.add(self.cases_frame, text="Test Cases")
        
        self.create_cases_view()

        # Flow Visualization View
        self.flow_frame = ttk.Frame(self.main_notebook)
        self.main_notebook.add(self.flow_frame, text="Flow Visualization")
        
        self.create_flow_view()

        # Start with suites view
        self.main_notebook.select(self.suites_frame)
        self.load_test_suites()

    def create_suites_view(self):
        """Create the test suites list view"""
        # Summary section
        summary_frame = ttk.LabelFrame(self.suites_frame, text="Test Summary", padding=15)
        summary_frame.pack(fill="x", pady=(0, 15))

        self.summary_label = ttk.Label(summary_frame, text="No test reports loaded", 
                                      font=('Segoe UI', 11))
        self.summary_label.pack(anchor="w")

        # Test suites list
        suites_list_frame = ttk.LabelFrame(self.suites_frame, text="Test Suites", padding=10)
        suites_list_frame.pack(fill="both", expand=True)

        tree_frame = ttk.Frame(suites_list_frame)
        tree_frame.pack(fill="both", expand=True)

        # Remove Actions column
        columns = ("Test Suite", "Status", "Total Cases", "Passed", "Failed", "Server Errors", "Success Rate")
        self.suites_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)

        # Configure column headings and widths
        self.suites_tree.heading("Test Suite", text="Test Suite")
        self.suites_tree.heading("Status", text="Status")
        self.suites_tree.heading("Total Cases", text="Total")
        self.suites_tree.heading("Passed", text="Passed")
        self.suites_tree.heading("Failed", text="Failed")
        self.suites_tree.heading("Server Errors", text="Server Errors")
        self.suites_tree.heading("Success Rate", text="Success Rate")

        self.suites_tree.column("Test Suite", width=250)
        self.suites_tree.column("Status", width=120)
        self.suites_tree.column("Total Cases", width=100)
        self.suites_tree.column("Passed", width=100)
        self.suites_tree.column("Failed", width=100)
        self.suites_tree.column("Server Errors", width=130)
        self.suites_tree.column("Success Rate", width=120)

        # Scrollbar for treeview
        suites_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.suites_tree.yview)
        self.suites_tree.configure(yscrollcommand=suites_scroll.set)

        self.suites_tree.pack(side="left", fill="both", expand=True)
        suites_scroll.pack(side="right", fill="y")

        # Bind selection event (remove execution-related events)
        self.suites_tree.bind("<Double-1>", self.on_suite_double_click)

    def create_cases_view(self):
        """Create the test cases list view"""
        # Test cases list
        cases_list_frame = ttk.LabelFrame(self.cases_frame, text="📋 Test Cases", padding=10)
        cases_list_frame.pack(fill="both", expand=True)

        tree_frame = ttk.Frame(cases_list_frame)
        tree_frame.pack(fill="both", expand=True)        # Add Test Type column to test cases view
        columns = ("Test Case", "Test Type", "Status", "Requests", "Server Errors", "Duration")
        self.cases_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)

        # Configure column headings and widths
        self.cases_tree.heading("Test Case", text="Test Case Name")
        self.cases_tree.heading("Test Type", text="Test Type")
        self.cases_tree.heading("Status", text="Status")
        self.cases_tree.heading("Requests", text="Requests")
        self.cases_tree.heading("Server Errors", text="Server Errors")
        self.cases_tree.heading("Duration", text="Duration")

        self.cases_tree.column("Test Case", width=250)
        self.cases_tree.column("Test Type", width=100)
        self.cases_tree.column("Status", width=120)
        self.cases_tree.column("Requests", width=100)
        self.cases_tree.column("Server Errors", width=150)
        self.cases_tree.column("Duration", width=120)

        # Scrollbar for treeview
        cases_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.cases_tree.yview)
        self.cases_tree.configure(yscrollcommand=cases_scroll.set)

        self.cases_tree.pack(side="left", fill="both", expand=True)
        cases_scroll.pack(side="right", fill="y")

        # Bind selection event (remove execution-related events)
        self.cases_tree.bind("<Double-1>", self.on_case_double_click)

    def create_flow_view(self):
        """Create the flow visualization view"""
        # Create paned window for flow view and details
        flow_paned = ttk.PanedWindow(self.flow_frame, orient=tk.HORIZONTAL)
        flow_paned.pack(fill="both", expand=True, padx=10, pady=10)

        # Flow visualization canvas (left side)
        flow_canvas_frame = ttk.LabelFrame(flow_paned, text="Operation Sequence", padding=10)
        flow_paned.add(flow_canvas_frame, weight=2)

        # Create canvas with scrollbars
        canvas_container = ttk.Frame(flow_canvas_frame)
        canvas_container.pack(fill="both", expand=True)

        self.flow_canvas = Canvas(canvas_container, bg="white", width=600, height=400)
        
        # Scrollbars for canvas
        h_scroll = ttk.Scrollbar(canvas_container, orient="horizontal", command=self.flow_canvas.xview)
        v_scroll = ttk.Scrollbar(canvas_container, orient="vertical", command=self.flow_canvas.yview)
        
        self.flow_canvas.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)
        
        self.flow_canvas.grid(row=0, column=0, sticky="nsew")
        h_scroll.grid(row=1, column=0, sticky="ew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        
        canvas_container.grid_rowconfigure(0, weight=1)
        canvas_container.grid_columnconfigure(0, weight=1)

        # Bind canvas events
        self.flow_canvas.bind("<Button-1>", self.on_canvas_click)
        self.flow_canvas.bind("<MouseWheel>", self.on_canvas_scroll)

        # Request details panel (right side)
        details_frame = ttk.LabelFrame(flow_paned, text="Request Details", padding=10)
        flow_paned.add(details_frame, weight=1)

        # Create notebook for request details
        self.details_notebook = ttk.Notebook(details_frame)
        self.details_notebook.pack(fill="both", expand=True)

        # Request tab
        request_frame = ttk.Frame(self.details_notebook)
        self.details_notebook.add(request_frame, text="Request")

        self.request_text = tk.Text(request_frame, wrap="word", font=('Consolas', 9))
        request_scroll = ttk.Scrollbar(request_frame, orient="vertical", command=self.request_text.yview)
        self.request_text.configure(yscrollcommand=request_scroll.set)
        self.request_text.pack(side="left", fill="both", expand=True)
        request_scroll.pack(side="right", fill="y")

        # Response tab
        response_frame = ttk.Frame(self.details_notebook)
        self.details_notebook.add(response_frame, text="Response")

        self.response_text = tk.Text(response_frame, wrap="word", font=('Consolas', 9))
        response_scroll = ttk.Scrollbar(response_frame, orient="vertical", command=self.response_text.yview)
        self.response_text.configure(yscrollcommand=response_scroll.set)
        self.response_text.pack(side="left", fill="both", expand=True)
        response_scroll.pack(side="right", fill="y")

        # Assertions tab
        assertions_frame = ttk.Frame(self.details_notebook)
        self.details_notebook.add(assertions_frame, text="Assertions")

        self.assertions_text = tk.Text(assertions_frame, wrap="word", font=('Consolas', 9))
        assertions_scroll = ttk.Scrollbar(assertions_frame, orient="vertical", command=self.assertions_text.yview)
        self.assertions_text.configure(yscrollcommand=assertions_scroll.set)
        self.assertions_text.pack(side="left", fill="both", expand=True)
        assertions_scroll.pack(side="right", fill="y")

    def load_test_suites(self):
        """Load test suites from the selected run's reports directory"""
        # Clear existing data
        for item in self.suites_tree.get_children():
            self.suites_tree.delete(item)
            
        # Get the selected run
        if not self.current_run_folder:
            selected_run = self.run_selector.get()
            if selected_run == "No runs available":
                self.summary_label.config(text="No test runs available")
                return
            
            # Find the run folder with this name
            run_folders = Paths.get_all_run_folders()
            for folder in run_folders:
                if folder.name == selected_run:
                    self.current_run_folder = folder
                    Paths.set_current_run_folder(folder)
        
        if not self.current_run_folder or not self.current_run_folder.exists():
            self.summary_label.config(text="Selected run folder does not exist")
            return
        
        # Create a new TestReportManager for the current run's reports directory
        # This ensures we're looking at the right reports folder for the selected run
        current_reports_dir = self.current_run_folder / "reports"
        if current_reports_dir.exists():
            # Temporarily create a new report manager with the specific reports folder
            temp_report_manager = TestReportManager()
            temp_report_manager.reports_folder = current_reports_dir
            temp_report_manager._load_reports()  # Reload reports from the new folder
            
            # Use the temporary report manager to get statistics
            stats = temp_report_manager.get_all_reports_statistics()
        else:
            stats = {
                'error': f'Reports directory not found in {self.current_run_folder.name}',
                'total_suites': 0,
                'total_cases': 0,
                'total_passed': 0,
                'total_failed': 0,
                'total_server_errors': 0,
                'overall_success_rate': 0.0,
                'suites': []
            }
        
        if 'error' in stats:
            self.summary_label.config(text=f"Error: {stats['error']}")
            return
            
        if stats['total_suites'] == 0:
            self.summary_label.config(text=f"No test reports found in run {self.current_run_folder.name}")
            return

        # Populate the treeview with suite details
        for suite in stats['suites']:
            if 'error' in suite:
                # Insert error row
                self.suites_tree.insert("", "end", values=(
                    suite['name'],
                    "ERROR",
                    "-", "-", "-", "-", "-"
                ))
            else:
                # Determine status icon
                if suite['status'] == "SERVER_ERROR":
                    status = "SERVER ERROR"
                elif suite['status'] == "FAILED":
                    status = "FAILED"
                else:
                    status = "PASSED"

                # Insert suite data
                self.suites_tree.insert("", "end", values=(
                    suite['name'],
                    status,
                    suite['total'],
                    suite['passed'],
                    suite['failed'],
                    suite['server_errors'],
                    f"{suite['success_rate']:.1f}%"
                ))

        # Update summary with centralized statistics
        summary_text = (f"Test Suites: {stats['total_suites']} | "
                       f"Total Cases: {stats['total_cases']} | "
                       f"Passed: {stats['total_passed']} | "
                       f"Failed: {stats['total_failed']} | "
                       f"Server Errors: {stats['total_server_errors']} | "
                       f"Success Rate: {stats['overall_success_rate']:.1f}%")
        
        self.summary_label.config(text=summary_text)
        self.app.update_status(f"Loaded {stats['total_suites']} test suites from run {self.current_run_folder.name}")

    def on_suite_double_click(self, event):
        """Handle double-click on test suite"""
        selection = self.suites_tree.selection()
        if not selection:
            return

        item = self.suites_tree.item(selection[0])
        suite_name = item['values'][0]
        
        self.show_test_cases(suite_name)

    def on_case_double_click(self, event):
        """Handle double-click on test case to show flow visualization"""
        selection = self.cases_tree.selection()
        if not selection:
            return

        item = self.cases_tree.item(selection[0])
        case_name = item['values'][0]
        
        # Store current test case
        self.current_test_case = case_name
        
        # Update breadcrumb
        self.breadcrumb_label.config(text=f"Test Suites > {self.current_test_suite} > {case_name}")
        
        # Switch to flow visualization view
        self.main_notebook.select(self.flow_frame)
        
        # Draw the operation flow for this test case
        self.draw_operation_flow(case_name)

    def show_test_suites_view(self):
        """Show the main test suites view"""
        self.current_test_suite = None
        self.current_test_case = None
        
        # Update breadcrumb
        self.breadcrumb_label.config(text="Test Suites")
        
        # Switch to suites view
        self.main_notebook.select(self.suites_frame)
        
        # Refresh test suites data
        self.load_test_suites()

    def show_test_cases(self, suite_name):
        """Show test cases for a specific suite"""
        self.current_test_suite = suite_name
        
        # Update breadcrumb
        self.breadcrumb_label.config(text=f"Test Suites > {suite_name}")
        
        # Switch to cases view
        self.main_notebook.select(self.cases_frame)
        
        # Load test cases
        self.load_test_cases(suite_name)

    def load_test_cases(self, suite_name):
        """Load test cases for a specific suite"""
        # Clear existing data
        for item in self.cases_tree.get_children():
            self.cases_tree.delete(item)
            
        reports_dir = Paths.get_reports()
        if not reports_dir:
            return
            
        report_file = reports_dir / f"{suite_name}.json"

        if not os.path.exists(report_file):
            return
            
        try:
            with open(report_file, 'r', encoding='utf-8') as f:
                report_data = json.load(f)
                
            if 'test_results' in report_data:
                for i, test_result in enumerate(report_data['test_results'], 1):
                    test_case_name = test_result.get('test_case_name', f'Test Case {i}')
                    success = test_result.get('success', False)
                    has_server_error = test_result.get('has_server_error', False)
                    requests = test_result.get('requests', [])                    # Extract test type and clean name using TestCaseGenerator methods
                    test_type = TestCaseGenerator.get_test_type_from_name(test_case_name)
                    clean_name = TestCaseGenerator.get_clean_test_name(test_case_name)
                    
                    # Determine status
                    if has_server_error:
                        status = "SERVER ERROR"
                    elif success:
                        status = "PASSED"
                    else:
                        status = "FAILED"
                    
                    # Count server errors in requests
                    server_error_count = sum(1 for req in requests if req.get('is_server_error', False))
                    
                    # Insert into treeview with test type column
                    self.cases_tree.insert("", "end", values=(
                        clean_name,
                        test_type,
                        status,
                        len(requests),
                        server_error_count,
                        "N/A"  # Duration placeholder
                    ))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load test cases: {str(e)}")

    def draw_operation_flow(self, case_name):
        """Draw the operation flow as a directed graph"""
        # Clear canvas
        self.flow_canvas.delete("all")
        self.node_positions = {}        # Load test case data
        reports_dir = Paths.get_reports()
        if not reports_dir:
            return
            
        report_file = reports_dir / f"{self.current_test_suite}.json"

        if not os.path.exists(report_file):
            return

        try:
            with open(report_file, 'r', encoding='utf-8') as f:
                report_data = json.load(f)            # Find the specific test case (try clean name first, then with extensions)
            test_case_data = None
            if 'test_results' in report_data:
                for test_result in report_data['test_results']:
                    test_case_name_in_report = test_result.get('test_case_name', '')
                    # Try exact match first
                    if test_case_name_in_report == case_name:
                        test_case_data = test_result
                        break
                    # Try with clean name comparison (remove extensions)
                    elif TestCaseGenerator.get_clean_test_name(test_case_name_in_report) == case_name:
                        test_case_data = test_result
                        break

            if not test_case_data:
                return

            requests = test_case_data.get('requests', [])
            if not requests:
                return

            # Store requests for node click handling
            self.current_requests = requests

            # Calculate positions for nodes
            self.calculate_node_positions(requests)
            
            # Draw connections (arrows)
            self.draw_connections(requests)
            
            # Draw nodes
            self.draw_nodes(requests)
            
            # Update canvas scroll region
            self.flow_canvas.configure(scrollregion=self.flow_canvas.bbox("all"))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to draw flow: {str(e)}")

    def calculate_node_positions(self, requests):
        """Calculate positions for all nodes in a vertical flow"""
        self.node_positions = {}
        
        if not requests:
            return
        
        # Force canvas to update its geometry
        self.flow_canvas.update_idletasks()
        
        # Get canvas dimensions, with fallback values
        canvas_width = self.flow_canvas.winfo_width()
        canvas_height = self.flow_canvas.winfo_height()
        
        # Use fallback dimensions if canvas isn't rendered yet
        if canvas_width <= 1:
            canvas_width = 800
        if canvas_height <= 1:
            canvas_height = 600
        
        # Center nodes horizontally
        center_x = canvas_width // 2
        
        # Calculate vertical spacing
        start_y = 80
        vertical_spacing = 120
        
        for i in range(len(requests)):
            y = start_y + (i * vertical_spacing)
            self.node_positions[i] = (center_x, y)

    def draw_connections(self, requests):
        """Draw vertical arrows connecting the nodes"""
        self.flow_canvas.delete("connection")
        
        if len(requests) < 2:
            return
            
        for i in range(len(requests) - 1):
            if i in self.node_positions and (i + 1) in self.node_positions:
                x1, y1 = self.node_positions[i]
                x2, y2 = self.node_positions[i + 1]
                
                # Draw vertical arrow from bottom of current node to top of next node
                start_y = y1 + self.node_height // 2 + 5
                end_y = y2 - self.node_height // 2 - 5
                
                # Draw the arrow line
                self.flow_canvas.create_line(
                    x1, start_y, x2, end_y,
                    fill="#666", width=3, tags="connection"
                )
                
                # Draw arrowhead
                arrow_size = 10
                self.flow_canvas.create_polygon(
                    x2, end_y,
                    x2 - arrow_size//2, end_y - arrow_size,
                    x2 + arrow_size//2, end_y - arrow_size,
                    fill="#666", outline="#666", tags="connection"
                )

    def draw_nodes(self, requests):
        """Draw rectangular nodes on the canvas"""
        if not requests or not self.node_positions:
            return
        
        self.node_items = {}  # Store canvas item IDs for click detection
        
        for i, request in enumerate(requests):
            if i not in self.node_positions:
                continue
                
            x, y = self.node_positions[i]
            
            # Determine node color based on request success and server errors
            is_server_error = request.get('is_server_error', False)
            is_success = request.get('success', False)
            
            if is_server_error:
                color = '#FF6B6B'  # Red for server errors
                border_color = '#8B0000'  # Dark red
                status_text = "ERROR"
            elif is_success:
                color = '#90EE90'  # Light green for success
                border_color = '#006400'  # Dark green
                status_text = "SUCCESS"
            else:
                color = '#FFD700'  # Gold for failures
                border_color = '#FF8C00'  # Dark orange
                status_text = "FAILED"
            
            # Draw the rectangular node
            node_id = self.flow_canvas.create_rectangle(
                x - self.node_width//2, y - self.node_height//2,
                x + self.node_width//2, y + self.node_height//2,
                fill=color, outline=border_color, width=3
            )
            
            # Get method for the label
            method = request.get('name', 'Unknown')
            if isinstance(request.get('data'), dict):
                method = request['data'].get('method', method)
            
            # Create label with method and status
            label = f"{method}\n{status_text}"
            
            # Draw the node label
            text_id = self.flow_canvas.create_text(
                x, y, text=label, font=('Arial', 9, 'bold'),
                fill='black', width=self.node_width-10, justify='center'
            )
            
            # Store both node and text IDs for this request
            self.node_items[node_id] = i
            self.node_items[text_id] = i
        
        # Bind click events to the canvas
        self.flow_canvas.bind("<Button-1>", self.on_node_click)

    def show_request_details_in_panel(self, request):
        """Show detailed information about a request"""
        # Clear existing content
        self.request_text.delete(1.0, tk.END)
        self.response_text.delete(1.0, tk.END)
        self.assertions_text.delete(1.0, tk.END)
        
        # Extract request data
        request_data = request.get('data', {})
        response_headers = request.get('response_headers', {})
        response_body = request.get('response_body', {})
        
        # Format request details
        method = request_data.get('method', 'Unknown')
        url_info = request_data.get('url', {})
        
        # Build URL string
        full_url = self.build_url_string(url_info)
        
        # Get headers and body
        headers = request_data.get('header', [])
        body = request_data.get('body', {})
        
        request_details = f"""Request Name: {request.get('name', 'Unknown')}
Method: {method}
URL: {full_url}

Headers:
{self.format_headers(headers)}

Body:
{self.format_body(body)}
"""
        
        # Response details
        response_details = f"""Response Headers:
{json.dumps(response_headers, indent=2)}

Response Body:
{json.dumps(response_body, indent=2) if response_body else 'Empty'}
"""
        
        # Assertions details
        is_server_error = request.get('is_server_error', False)
        assertions = request.get('assertions', [])
        
        assertions_details = f"""Request Success: {request.get('success', False)}
Server Error: {'Yes' if is_server_error else 'No'}

Assertions:
"""
        
        if assertions:
            for assertion in assertions:
                assertion_text = assertion.get('assertion', 'Unknown')
                error = assertion.get('error')
                if error:
                    assertions_details += f"{assertion_text}: {error}\n"
                else:
                    assertions_details += f"{assertion_text}: Passed\n"
        else:
            assertions_details += "No assertions recorded\n"
        
        # Insert content into text widgets
        self.request_text.config(state=tk.NORMAL)
        self.response_text.config(state=tk.NORMAL)
        self.assertions_text.config(state=tk.NORMAL)
        
        # Clear and insert new content from the beginning
        self.request_text.delete(1.0, tk.END)
        self.request_text.insert(1.0, request_details)
        
        self.response_text.delete(1.0, tk.END)
        self.response_text.insert(1.0, response_details)
        
        self.assertions_text.delete(1.0, tk.END)
        self.assertions_text.insert(1.0, assertions_details)
        
        self.request_text.config(state=tk.DISABLED)
        self.response_text.config(state=tk.DISABLED)
        self.assertions_text.config(state=tk.DISABLED)

    def build_url_string(self, url_info):
        """Build a complete URL string from URL info"""
        if isinstance(url_info, str):
            return url_info
        
        if not isinstance(url_info, dict):
            return "Unknown URL"
        
        # Extract components
        host_parts = url_info.get('host', [])
        path_parts = url_info.get('path', [])
        query_params = url_info.get('query', [])
        
        # Build URL
        if host_parts:
            if isinstance(host_parts, list):
                host = '.'.join(str(part) for part in host_parts)
            else:
                host = str(host_parts)
        else:
            host = "{{baseUrl}}"
        
        if path_parts:
            if isinstance(path_parts, list):
                path = '/' + '/'.join(str(part) for part in path_parts)
            else:
                path = str(path_parts)
        else:
            path = ""
        
        url = f"http://{host}{path}"
        
        # Add query parameters
        if query_params and isinstance(query_params, list):
            query_strings = []
            for param in query_params:
                if isinstance(param, dict):
                    key = param.get('key', '')
                    value = param.get('value', '')
                    query_strings.append(f"{key}={value}")
            if query_strings:
                url += "?" + "&".join(query_strings)
        
        return url

    def format_headers(self, headers):
        """Format headers for display"""
        if not headers:
            return "None"
        
        if isinstance(headers, list):
            header_dict = {}
            for header in headers:
                if isinstance(header, dict):
                    key = header.get('key', '')
                    value = header.get('value', '')
                    header_dict[key] = value
            return json.dumps(header_dict, indent=2)
        
        return json.dumps(headers, indent=2)

    def format_body(self, body):
        """Format request body for display"""
        if not body:
            return "None"
        
        if isinstance(body, dict):
            if 'raw' in body:
                return body['raw']
            elif 'formdata' in body:
                return json.dumps(body['formdata'], indent=2)
            else:
                return json.dumps(body, indent=2)
        
        return str(body)

    def on_canvas_click(self, event):
        """Handle click on canvas to show request details"""
        # Get the item that was clicked
        clicked_item = self.flow_canvas.find_closest(event.x, event.y)[0]
        
        # Check if this item corresponds to a request node
        if hasattr(self, 'node_items') and clicked_item in self.node_items:
            request_index = self.node_items[clicked_item]
            if hasattr(self, 'current_requests') and request_index < len(self.current_requests):
                request = self.current_requests[request_index]
                self.show_request_details_in_panel(request)

    def on_canvas_scroll(self, event):
        """Handle mouse wheel scrolling on canvas"""
        # Scroll vertically
        self.flow_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def on_node_click(self, event):
        """Handle click on a specific node"""
        # Get the item that was clicked
        clicked_item = self.flow_canvas.find_closest(event.x, event.y)[0]
        
        # Check if this item corresponds to a request node
        if hasattr(self, 'node_items') and clicked_item in self.node_items:
            request_index = self.node_items[clicked_item]
            if hasattr(self, 'current_requests') and request_index < len(self.current_requests):
                request = self.current_requests[request_index]
                self.show_request_details_in_panel(request)

    def refresh_run_list(self):
        """Refresh the list of available runs"""
        # Get all run folders
        run_folders = Paths.get_all_run_folders()
        
        # Sort runs by creation time (newest first)
        run_folders.sort(key=lambda x: x.stat().st_ctime, reverse=True)
        
        # Store current selection if any
        current_selection = self.run_selector.get() if self.run_selector.get() != "No runs available" else None
        selected_index = 0
        
        # Update the run selector dropdown
        if run_folders:
            run_names = [folder.name for folder in run_folders]
            self.run_selector['values'] = run_names
            
            # If there was a previous selection, try to maintain it
            if current_selection and current_selection in run_names:
                selected_index = run_names.index(current_selection)
                
            self.run_selector.current(selected_index)
            self.current_run_folder = run_folders[selected_index]
            Paths.set_current_run_folder(run_folders[selected_index])
        else:
            self.run_selector['values'] = ["No runs available"]
            self.run_selector.current(0)
            self.current_run_folder = None
        
        # Load test suites for the selected run
        self.load_test_suites()

    def on_run_selected(self, event):
        """Handle run selection change"""
        selected_run = self.run_selector.get()
        if selected_run == "No runs available":
            return
            
        # Reset current run folder to force reload
        self.current_run_folder = None
        
        # Find the run folder with this name
        run_folders = Paths.get_all_run_folders()
        for folder in run_folders:
            if folder.name == selected_run:
                self.current_run_folder = folder
                Paths.set_current_run_folder(folder)
                break
                
        # Load test suites for the selected run
        self.load_test_suites()

    def delete_current_run(self):
        """Delete the currently selected run folder"""
        selected_run = self.run_selector.get()
        if selected_run == "No runs available":
            messagebox.showinfo("Info", "No run selected to delete")
            return
            
        # Confirm deletion
        result = messagebox.askokcancel(
            "Confirm Delete",
            f"Are you sure you want to delete the entire run '{selected_run}'?\n\n"
            f"This will permanently delete all test suites, test cases, and reports for this run.",
            icon="warning"
        )
        
        if not result:
            return

        try:
            # Find the run folder with this name
            run_folders = Paths.get_all_run_folders()
            for folder in run_folders:
                if folder.name == selected_run:
                    # Delete the run folder
                    shutil.rmtree(folder)
                    self.app.update_status(f"Deleted run folder: {selected_run}")
                    messagebox.showinfo("Success", f"Run '{selected_run}' deleted successfully")
                    
                    # Refresh the run list
                    self.refresh_run_list()
                    return
                    
            messagebox.showinfo("Error", f"Run folder '{selected_run}' not found")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete run: {str(e)}")