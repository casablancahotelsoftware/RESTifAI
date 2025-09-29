import tkinter as tk
from tkinter import ttk, messagebox
import os
import json
import shutil
from pathlib import Path
from postman_collection_builder import PostmanCollectionBuilder
from test_case_generator import TestCaseGenerator
from config import Paths

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

class TestsTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.current_test_suite = None
        self.current_run_folder = None
        self.create_ui()
        self.refresh_run_list()
        
    def create_ui(self):
        """Create the Tests tab UI"""
        # Main container with padding
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Title
        title_label = ttk.Label(main_frame, text="Test Overview and Execution", 
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

        refresh_btn = ttk.Button(controls_frame, text="Refresh", 
                                command=self.load_test_suites)
        refresh_btn.pack(side="left", padx=(0, 10))

        back_btn = ttk.Button(controls_frame, text="Back to Suites", 
                             command=self.show_test_suites_view)
        back_btn.pack(side="left", padx=(0, 10))

        execute_all_btn = ttk.Button(controls_frame, text="Execute All Collections", 
                                    command=self.execute_all_test_suites)
        execute_all_btn.pack(side="left", padx=(0, 10))

        delete_btn = ttk.Button(controls_frame, text="Delete Selected", 
                               command=self.delete_selected_item)
        delete_btn.pack(side="left", padx=(0, 10))

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

        # Collection Details View
        self.details_frame = ttk.Frame(self.main_notebook)
        self.main_notebook.add(self.details_frame, text="Collection Details")
        self.create_details_view()

        # Start with suites view
        self.main_notebook.select(self.suites_frame)
        self.load_test_suites()

    def create_suites_view(self):
        """Create the test suites list view"""
        # Test suites list
        suites_list_frame = ttk.LabelFrame(self.suites_frame, text="Test Suites", padding=10)
        suites_list_frame.pack(fill="both", expand=True)

        tree_frame = ttk.Frame(suites_list_frame)
        tree_frame.pack(fill="both", expand=True)

        columns = ("Test Suite", "Test Cases", "Last Modified")
        self.suites_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)

        # Configure column headings and widths
        self.suites_tree.heading("Test Suite", text="Test Suite Name")
        self.suites_tree.heading("Test Cases", text="Test Cases")
        self.suites_tree.heading("Last Modified", text="Last Modified")

        self.suites_tree.column("Test Suite", width=300)
        self.suites_tree.column("Test Cases", width=100)
        self.suites_tree.column("Last Modified", width=200)

        # Scrollbar for treeview
        suites_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.suites_tree.yview)
        self.suites_tree.configure(yscrollcommand=suites_scroll.set)

        self.suites_tree.pack(side="left", fill="both", expand=True)
        suites_scroll.pack(side="right", fill="y")

        # Bind selection and click events
        self.suites_tree.bind("<Double-1>", self.on_suite_double_click)
        self.suites_tree.bind("<Button-3>", self.on_suite_right_click)  # Right-click for context menu

    def create_cases_view(self):
        """Create the test cases list view"""
        # Test cases list
        cases_list_frame = ttk.LabelFrame(self.cases_frame, text="Test Cases", padding=10)
        cases_list_frame.pack(fill="both", expand=True)

        tree_frame = ttk.Frame(cases_list_frame)
        tree_frame.pack(fill="both", expand=True)
        
        columns = ("Test Case", "Test Type", "Collection File", "File Size", "Last Modified")
        self.cases_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)

        # Configure column headings and widths
        self.cases_tree.heading("Test Case", text="Test Case Name")
        self.cases_tree.heading("Test Type", text="Test Type")
        self.cases_tree.heading("Collection File", text="Collection File")
        self.cases_tree.heading("File Size", text="File Size")
        self.cases_tree.heading("Last Modified", text="Last Modified")

        self.cases_tree.column("Test Case", width=250)
        self.cases_tree.column("Test Type", width=100)
        self.cases_tree.column("Collection File", width=250)
        self.cases_tree.column("File Size", width=100)
        self.cases_tree.column("Last Modified", width=200)

        # Scrollbar for treeview
        cases_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.cases_tree.yview)
        self.cases_tree.configure(yscrollcommand=cases_scroll.set)

        self.cases_tree.pack(side="left", fill="both", expand=True)
        cases_scroll.pack(side="right", fill="y")

        # Bind selection and click events
        self.cases_tree.bind("<Double-1>", self.on_case_double_click)
        self.cases_tree.bind("<Button-3>", self.on_case_right_click)  # Right-click for context menu

    def create_details_view(self):
        """Create the collection details view"""
        # Collection details
        details_frame = ttk.LabelFrame(self.details_frame, text="Postman Collection Details", padding=10)
        details_frame.pack(fill="both", expand=True)

        # Create text widget with scrollbar
        text_frame = ttk.Frame(details_frame)
        text_frame.pack(fill="both", expand=True)

        self.details_text = tk.Text(text_frame, wrap="none", font=('Consolas', 10))
        
        # Scrollbars
        v_scroll = ttk.Scrollbar(text_frame, orient="vertical", command=self.details_text.yview)
        h_scroll = ttk.Scrollbar(text_frame, orient="horizontal", command=self.details_text.xview)
        
        self.details_text.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        
        self.details_text.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")
        
        text_frame.grid_rowconfigure(0, weight=1)
        text_frame.grid_columnconfigure(0, weight=1)

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

    def load_test_suites(self):
        """Load test suites from the selected run's tests directory"""
        # Clear existing data
        for item in self.suites_tree.get_children():
            self.suites_tree.delete(item)
        
        # Get the selected run
        if not self.current_run_folder:
            selected_run = self.run_selector.get()
            if selected_run == "No runs available":
                self.app.update_status("No test runs available")
                return
            
            # Find the run folder with this name
            run_folders = Paths.get_all_run_folders()
            for folder in run_folders:
                if folder.name == selected_run:
                    self.current_run_folder = folder
                    Paths.set_current_run_folder(folder)
        
        if not self.current_run_folder or not self.current_run_folder.exists():
            self.app.update_status("Selected run folder does not exist")
            return
            
        # Get the tests directory for this run
        tests_dir = self.current_run_folder / Paths.TESTS
        
        if not tests_dir.exists():
            self.app.update_status(f"No tests directory found in run {self.current_run_folder.name}")
            return

        # Look for test suite folders
        try:
            for item in tests_dir.iterdir():
                if item.is_dir():
                    # Count test case collections in this suite
                    collection_files = [f for f in item.iterdir() 
                                      if f.name.endswith('.postman_collection.json')]
                    
                    # Get last modified time
                    last_modified = item.stat().st_mtime
                    last_modified_str = self.format_timestamp(last_modified)
                    
                    # Insert into treeview
                    self.suites_tree.insert("", "end", values=(
                        item.name,
                        len(collection_files),
                        last_modified_str
                    ))

            self.app.update_status(f"Loaded test suites from {self.current_run_folder.name}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load test suites: {str(e)}")

    def load_test_cases(self, suite_name):
        """Load test cases for a specific suite"""
        # Clear existing data
        for item in self.cases_tree.get_children():
            self.cases_tree.delete(item)

        tests_dir = Paths.get_tests()
        if not tests_dir:
            return
            
        suite_dir = tests_dir / suite_name

        if not suite_dir.exists():
            return

        try:
            collection_files = list(suite_dir.glob('*.postman_collection.json'))
            
            for collection_file in collection_files:
                file_path = collection_file                # Extract test case name from filename
                test_case_name = collection_file.name.replace('.postman_collection.json', '')
                if test_case_name.startswith(suite_name + '_'):
                    test_case_name = test_case_name[len(suite_name) + 1:]                # Extract test type and clean name using TestCaseGenerator methods
                test_type = TestCaseGenerator.get_test_type_from_name(test_case_name)
                clean_name = TestCaseGenerator.get_clean_test_name(test_case_name)
                
                # Get file stats
                file_stats = file_path.stat()
                file_size = self.format_file_size(file_stats.st_size)
                last_modified = self.format_timestamp(file_stats.st_mtime)
                
                # Insert into treeview with test type column
                self.cases_tree.insert("", "end", values=(
                    clean_name,
                    test_type,
                    collection_file,
                    file_size,
                    last_modified
                ))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load test cases: {str(e)}")

    def show_collection_details(self, suite_name, collection_file):
        """Show detailed Postman collection content"""
        tests_dir = Paths.get_tests()
        if not tests_dir:
            self.details_text.delete(1.0, tk.END)
            self.details_text.insert(1.0, "No run selected.")
            return
            
        file_path = tests_dir / suite_name / collection_file

        if not file_path.exists():
            self.details_text.delete(1.0, tk.END)
            self.details_text.insert(1.0, "Collection file not found.")
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                collection_data = json.load(f)
            
            # Format JSON with proper indentation
            formatted_json = json.dumps(collection_data, indent=2, ensure_ascii=False)
            
            # Clear and insert content
            self.details_text.delete(1.0, tk.END)
            self.details_text.insert(1.0, formatted_json)
            
        except Exception as e:
            self.details_text.delete(1.0, tk.END)
            self.details_text.insert(1.0, f"Error loading collection: {str(e)}")

    def on_suite_double_click(self, event):
        """Handle double-click on test suite"""
        selection = self.suites_tree.selection()
        if not selection:
            return

        item = self.suites_tree.item(selection[0])
        suite_name = item['values'][0]
        
        self.show_test_cases(suite_name)

    def on_case_double_click(self, event):
        """Handle double-click on test case"""
        selection = self.cases_tree.selection()
        if not selection:
            return

        item = self.cases_tree.item(selection[0])
        collection_file = item['values'][2]  # Collection file is now at index 2
        
        # Show collection details
        self.show_collection_details(self.current_test_suite, collection_file)
        
        # Update breadcrumb
        test_case_name = item['values'][0]
        self.breadcrumb_label.config(text=f"Test Suites > {self.current_test_suite} > {test_case_name}")
        
        # Switch to details view
        self.main_notebook.select(self.details_frame)

    def show_test_suites_view(self):
        """Show the main test suites view"""
        self.current_test_suite = None
        
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

    def delete_selected_item(self):
        """Delete the selected test suite or test case"""
        current_tab = self.main_notebook.index(self.main_notebook.select())
        
        if current_tab == 0:  # Test suites view
            self.delete_test_suite()
        elif current_tab == 1:  # Test cases view
            self.delete_test_case()
        else:
            messagebox.showinfo("Info", "Select a test suite or test case to delete")

    def delete_test_suite(self):
        """Delete an entire test suite"""
        selection = self.suites_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a test suite to delete")
            return

        item = self.suites_tree.item(selection[0])
        suite_name = item['values'][0]
        
        # Confirm deletion
        result = messagebox.askyesno(
            "Confirm Deletion",
            f"Are you sure you want to delete the entire test suite '{suite_name}' and all its test cases?\n\nThis action cannot be undone."
        )
        
        if not result:
            return

        try:
            tests_dir = Paths.get_tests()
            if not tests_dir:
                messagebox.showerror("Error", "No run selected.")
                return
                
            suite_dir = tests_dir / suite_name
            
            if os.path.exists(suite_dir):
                import shutil
                shutil.rmtree(suite_dir)
                
            # Remove from treeview
            self.suites_tree.delete(selection[0])
            
            messagebox.showinfo("Success", f"Test suite '{suite_name}' deleted successfully")
            self.app.update_status(f"Deleted test suite: {suite_name}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete test suite: {str(e)}")

    def delete_test_case(self):
        """Delete a specific test case"""
        selection = self.cases_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a test case to delete")
            return
            
        item = self.cases_tree.item(selection[0])
        test_case_name = item['values'][0]
        collection_file = item['values'][2]  # Collection file is now at index 2
        
        # Confirm deletion
        result = messagebox.askyesno(
            "Confirm Deletion",
            f"Are you sure you want to delete the test case '{test_case_name}'?\n\nThis will delete the file: {collection_file}\n\nThis action cannot be undone."
        )
        
        if not result:
            return

        try:
            tests_dir = Paths.get_tests()
            if not tests_dir:
                messagebox.showerror("Error", "No run selected.")
                return
                
            file_path = tests_dir / self.current_test_suite / collection_file
            
            if os.path.exists(file_path):
                os.remove(file_path)
                
            # Remove from treeview
            self.cases_tree.delete(selection[0])
            
            messagebox.showinfo("Success", f"Test case '{test_case_name}' deleted successfully")
            self.app.update_status(f"Deleted test case: {test_case_name}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete test case: {str(e)}")

    def execute_all_test_suites(self):
        """Execute all Postman collections in the selected run"""
        if not self.current_run_folder:
            messagebox.showerror("Error", "No run selected")
            return
    
        try:
            self.app.update_status(f"Executing all collections in run {self.current_run_folder.name}...")
            
            # Get the tests directory
            tests_dir = self.current_run_folder / Paths.TESTS
            if not tests_dir.exists():
                messagebox.showerror("Error", f"Tests directory not found in run {self.current_run_folder.name}")
                return
                
            PostmanCollectionBuilder.execute_all_test_suites(tests_dir, self.app.environment_initializer)
            
            messagebox.showinfo("Success", "All collections executed successfully")
            self.app.update_status("All collections executed successfully")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to execute collections:\n{str(e)}")
            self.app.update_status("Collection execution failed")

    def execute_test_suite(self, suite_name):
        """Execute a specific test suite"""
        if not self.current_run_folder:
            messagebox.showerror("Error", "No run selected")
            return
            
        tests_dir = Paths.get_tests()
        if not tests_dir:
            messagebox.showerror("Error", "No run selected.")
            return
            
        suite_folder = tests_dir / suite_name
        
        if not os.path.exists(suite_folder):
            messagebox.showerror("Error", f"Test suite folder not found: {suite_folder}")
            return
        
        try:
            self.app.update_status(f"Executing test suite: {suite_name}...")
            
            PostmanCollectionBuilder.execute_test_suite_collections(suite_folder, self.app.environment_initializer)
            
            messagebox.showinfo("Success", f"Test suite '{suite_name}' executed successfully")
            self.app.update_status(f"Test suite '{suite_name}' executed successfully")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to execute test suite '{suite_name}':\n{str(e)}")
            self.app.update_status(f"Test suite execution failed: {suite_name}")

    def execute_test_case(self, case_name):
        """Execute a specific test case"""
        tests_dir = Paths.get_tests()
        if not tests_dir:
            messagebox.showerror("Error", "No run selected.")
            return
            
        suite_folder = tests_dir / self.current_test_suite
        
        if not os.path.exists(suite_folder):
            messagebox.showerror("Error", f"Test suite folder not found: {suite_folder}")
            return
        
        # Find the collection file for this test case
        collection_files = list(suite_folder.glob('*.postman_collection.json'))
        target_file = None
        
        for collection_file in collection_files:
            # Check if this collection file matches the test case name
            if case_name in collection_file.name or collection_file.name.startswith(f"{self.current_test_suite}_{case_name}"):
                target_file = collection_file
                break
        
        if not target_file:
            messagebox.showerror("Error", f"Test case collection file not found for: {case_name}")
            return
        
        try:
            self.app.update_status(f"Executing test case: {case_name}...")
            
            PostmanCollectionBuilder.execute_collection(target_file, self.app.environment_initializer)
            
            messagebox.showinfo("Success", f"Test case '{case_name}' executed successfully")
            self.app.update_status(f"Test case '{case_name}' executed successfully")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to execute test case '{case_name}':\n{str(e)}")
            self.app.update_status(f"Test case execution failed: {case_name}")

    def format_timestamp(self, timestamp):
        """Format timestamp to readable string"""
        import datetime
        try:
            dt = datetime.datetime.fromtimestamp(timestamp)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            return "Unknown"

    def format_file_size(self, size_bytes):
        """Format file size to human readable string"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"

    def on_suite_right_click(self, event):
        """Handle right-click on test suite to show context menu"""
        selection = self.suites_tree.selection()
        if not selection:
            return

        item = self.suites_tree.item(selection[0])
        suite_name = item['values'][0]
        
        # Create context menu
        context_menu = tk.Menu(self, tearoff=0)
        context_menu.add_command(label="▶Execute Test Suite", 
                                command=lambda: self.execute_test_suite(suite_name))
        context_menu.add_separator()
        context_menu.add_command(label="View Test Cases", 
                                command=lambda: self.show_test_cases(suite_name))
        context_menu.add_command(label="Delete Suite", 
                                command=lambda: self.delete_test_suite())
        
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()

    def on_case_right_click(self, event):
        """Handle right-click on test case to show context menu"""
        selection = self.cases_tree.selection()
        if not selection:
            return

        item = self.cases_tree.item(selection[0])
        case_name = item['values'][0]
        
        # Create context menu
        context_menu = tk.Menu(self, tearoff=0)
        context_menu.add_command(label="Execute Test Case", 
                                command=lambda: self.execute_test_case(case_name))
        context_menu.add_separator()
        context_menu.add_command(label="View Details", 
                                command=lambda: self.on_case_double_click(event))
        context_menu.add_command(label="Delete Test Case", 
                                command=lambda: self.delete_test_case())
        
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()

    def on_run_selected(self, event):
        """Handle run selection change"""
        selected_run = self.run_selector.get()
        if selected_run == "No runs available":
            return
            
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