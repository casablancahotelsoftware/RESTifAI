import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
from config import Paths
from spec_parser import OpenAPISpecParser

class SpecificationTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.create_ui()

    def create_ui(self):
        """Create the specification UI"""
        # Main container with padding
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Title
        title_label = ttk.Label(main_frame, text="OpenAPI Specification", 
                               font=('Segoe UI', 16, 'bold'))
        title_label.pack(anchor="w", pady=(0, 20))

        # File Selection Section
        file_frame = ttk.LabelFrame(main_frame, text="Specification File", padding=15)
        file_frame.pack(fill="x", pady=(0, 20))

        # File path entry and browse button
        path_frame = ttk.Frame(file_frame)
        path_frame.pack(fill="x", pady=5)

        self.spec_entry = ttk.Entry(path_frame, textvariable=self.app.spec_file_var, width=60)
        self.spec_entry.pack(side="left", fill="x", expand=True)

        browse_btn = ttk.Button(path_frame, text="Browse", command=self.browse_spec_file)
        browse_btn.pack(side="right", padx=(10, 0))

        # Validation button
        button_frame = ttk.Frame(file_frame)
        button_frame.pack(fill="x", pady=(10, 0))

        validate_btn = ttk.Button(button_frame, text="Validate Specification", 
                                 command=self.validate_specification)
        validate_btn.pack(side="left")

        # Specification Info Section
        info_frame = ttk.LabelFrame(main_frame, text="Specification Information", padding=15)
        info_frame.pack(fill="both", expand=True, pady=(0, 20))

        # Create scrollable text widget for spec info
        text_frame = ttk.Frame(info_frame)
        text_frame.pack(fill="both", expand=True)

        self.info_text = tk.Text(text_frame, wrap="word", height=15, font=('Consolas', 10))
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.info_text.yview)
        self.info_text.configure(yscrollcommand=scrollbar.set)

        self.info_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Quick Access Section
        quick_frame = ttk.LabelFrame(main_frame, text="Quick Access", padding=15)
        quick_frame.pack(fill="x")

        continue_btn = ttk.Button(quick_frame, text="Continue to Endpoints", 
                                 command=self.continue_to_endpoints)
        continue_btn.pack(side="left")

    def browse_spec_file(self):
        """Browse for OpenAPI specification file"""
        filename = filedialog.askopenfilename(
            title="Select OpenAPI Specification File",
            filetypes=[
                ("JSON files", "*.json"),
                ("YAML files", "*.yaml *.yml"),
                ("All files", "*.*")            ],
            initialdir=Paths.get_specifications()
        )
        if filename:
            self.app.spec_file_var.set(filename)
            self.app.update_status(f"Selected specification: {os.path.basename(filename)}")
            # Automatically load the specification after selection
            self.load_specification()

    def load_specification(self):
        """Load and parse the OpenAPI specification"""
        spec_file = self.app.spec_file_var.get()
        if not spec_file:
            messagebox.showwarning("Warning", "Please select a specification file first")
            return

        if not os.path.exists(spec_file):
            messagebox.showerror("Error", "Specification file not found")
            return

        try:
            self.app.update_status("Loading specification...")
            
            self.app.parser = OpenAPISpecParser(spec_file)
            self.app.endpoints = self.app.parser.get_endpoints()
            self.app.spec = self.app.parser.spec

            # Display specification information
            self.display_spec_info()

            messagebox.showinfo("Success", "Specification loaded successfully!")
            self.app.update_status(f"Loaded {len(self.app.endpoints)} endpoints from specification")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load specification:\n{str(e)}")
            self.app.update_status("Failed to load specification")

    def validate_specification(self):
        """Validate the current specification"""
        if not self.app.spec:
            messagebox.showwarning("Warning", "Please load a specification first")
            return

        try:
            # Basic validation
            errors = []
            
            # Check for required fields
            if "openapi" not in self.app.spec:
                errors.append("Missing 'openapi' version field")
            
            if "info" not in self.app.spec:
                errors.append("Missing 'info' section")
            
            if "paths" not in self.app.spec or not self.app.spec["paths"]:
                errors.append("No paths defined")

            # Check endpoints
            if not self.app.endpoints:
                errors.append("No valid endpoints found")

            if errors:
                error_msg = "Validation errors found:\n" + "\n".join(f"• {error}" for error in errors)
                messagebox.showwarning("Validation Issues", error_msg)
            else:
                messagebox.showinfo("Validation", "Specification is valid!")
                
            self.app.update_status("Specification validation completed")

        except Exception as e:
            messagebox.showerror("Error", f"Validation failed:\n{str(e)}")

    def display_spec_info(self):
        """Display specification information in the text widget"""
        self.info_text.delete(1.0, tk.END)
        
        if not self.app.spec:
            self.info_text.insert(tk.END, "No specification loaded")
            return

        info_lines = []
        
        # Basic info
        info_lines.append("=== SPECIFICATION OVERVIEW ===")
        info_lines.append(f"OpenAPI Version: {self.app.spec.get('openapi', 'Unknown')}")
        
        if "info" in self.app.spec:
            info = self.app.spec["info"]
            info_lines.append(f"Title: {info.get('title', 'Unknown')}")
            info_lines.append(f"Version: {info.get('version', 'Unknown')}")
            if "description" in info:
                info_lines.append(f"Description: {info['description']}")

        # Server info
        if "servers" in self.app.spec:
            info_lines.append("\n=== SERVERS ===")
            for i, server in enumerate(self.app.spec["servers"]):
                info_lines.append(f"Server {i+1}: {server.get('url', 'Unknown')}")
                if "description" in server:
                    info_lines.append(f"  Description: {server['description']}")

        # Endpoints summary
        info_lines.append(f"\n=== ENDPOINTS SUMMARY ===")
        info_lines.append(f"Total Endpoints: {len(self.app.endpoints)}")
        
        # Group by HTTP method
        methods = {}
        for endpoint in self.app.endpoints:
            method = endpoint.method.upper()
            if method not in methods:
                methods[method] = 0
            methods[method] += 1
        
        for method, count in sorted(methods.items()):
            info_lines.append(f"{method}: {count} endpoints")

        # Detailed endpoints
        info_lines.append(f"\n=== ENDPOINT DETAILS ===")
        for endpoint in self.app.endpoints:  # Show first 20
            info_lines.append(f"{endpoint.method.upper()} {endpoint.path}")
            info_lines.append(f"  Operation ID: {endpoint.operation_id}")
            if hasattr(endpoint, 'summary') and endpoint.summary:
                info_lines.append(f"  Summary: {endpoint.summary}")
            info_lines.append("")

        if len(self.app.endpoints) > 20:
            info_lines.append(f"... and {len(self.app.endpoints) - 20} more endpoints")

        # Display the information
        self.info_text.insert(tk.END, "\n".join(info_lines))

    def continue_to_endpoints(self):
        """Continue to the endpoints tab"""
        if not self.app.spec:
            messagebox.showwarning("Warning", "Please load a specification first")
            return

        self.app.switch_to_endpoints()
        self.app.update_status("Switched to endpoints selection")