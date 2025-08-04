"""
ClaudeSync GUI - Settings View
"""
import customtkinter as ctk
from tkinter import messagebox
import json
from pathlib import Path
from typing import Dict, Any


class SettingsView:
    def __init__(self, parent_frame, gui_instance):
        self.parent = parent_frame
        self.gui = gui_instance
        self.settings = {}
        self.setting_widgets = {}
        
    def show(self):
        """Display the settings view"""
        # Clear parent frame
        for widget in self.parent.winfo_children():
            widget.destroy()
            
        # Title
        title = ctk.CTkLabel(
            self.parent,
            text="Settings",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title.pack(pady=(20, 10))
        
        # Load current settings
        self.load_settings()
        
        # Create tabview for different setting categories
        self.tabview = ctk.CTkTabview(self.parent, width=600, height=400)
        self.tabview.pack(pady=20, padx=20, fill="both", expand=True)
        
        # Add tabs
        self.tabview.add("General")
        self.tabview.add("Sync")
        self.tabview.add("Advanced")
        
        # Populate tabs
        self.create_general_settings()
        self.create_sync_settings()
        self.create_advanced_settings()
        
        # Save button
        save_btn = ctk.CTkButton(
            self.parent,
            text="Save Settings",
            command=self.save_settings,
            width=150,
            height=40
        )
        save_btn.pack(pady=10)
        
    def load_settings(self):
        """Load current settings"""
        # Get global settings
        result = self.gui.run_csync_command(["config", "ls"])
        
        if result.returncode == 0:
            # Parse settings from output
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if ":" in line and not line.startswith("Local settings") and not line.startswith("Global settings"):
                    key, value = line.split(":", 1)
                    self.settings[key.strip()] = value.strip()
                    
    def create_general_settings(self):
        """Create general settings tab"""
        tab = self.tabview.tab("General")
        
        # Log level
        self.create_setting_widget(
            tab,
            "log_level",
            "Log Level",
            "dropdown",
            ["DEBUG", "INFO", "WARNING", "ERROR"],
            "Set the verbosity of logging"
        )
        
        # Max file size
        self.create_setting_widget(
            tab,
            "max_file_size",
            "Max File Size (bytes)",
            "number",
            None,
            "Maximum size for individual files"
        )
        
        # Upload delay
        self.create_setting_widget(
            tab,
            "upload_delay",
            "Upload Delay (seconds)",
            "number",
            None,
            "Delay between file uploads to prevent rate limiting"
        )
        
    def create_sync_settings(self):
        """Create sync settings tab"""
        tab = self.tabview.tab("Sync")
        
        # Two-way sync
        self.create_setting_widget(
            tab,
            "two_way_sync",
            "Two-way Sync",
            "boolean",
            None,
            "Enable bidirectional synchronization"
        )
        
        # Prune remote files
        self.create_setting_widget(
            tab,
            "prune_remote_files",
            "Prune Remote Files",
            "boolean",
            None,
            "Delete remote files not present locally"
        )
        
        # Compression
        self.create_setting_widget(
            tab,
            "compression_algorithm",
            "Compression Algorithm",
            "dropdown",
            ["none", "zlib", "brotli", "bz2", "lzma", "pack"],
            "File compression method"
        )
        
    def create_advanced_settings(self):
        """Create advanced settings tab"""
        tab = self.tabview.tab("Advanced")
        
        # Active provider
        self.create_setting_widget(
            tab,
            "active_provider",
            "API Provider",
            "text",
            None,
            "Current API provider (read-only)",
            readonly=True
        )
        
        # Submodule detection
        info_label = ctk.CTkLabel(
            tab,
            text="Submodule Detection Filenames:",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        info_label.pack(pady=(10, 5), anchor="w", padx=20)
        
        desc_label = ctk.CTkLabel(
            tab,
            text="Files that indicate a submodule directory",
            font=ctk.CTkFont(size=10),
            text_color="gray"
        )
        desc_label.pack(anchor="w", padx=20)
        
        # Text area for submodule filenames
        self.submodule_text = ctk.CTkTextbox(tab, width=500, height=100)
        self.submodule_text.pack(pady=10, padx=20, fill="x")
        
        # Load submodule filenames
        if "submodule_detect_filenames" in self.settings:
            try:
                filenames = json.loads(self.settings["submodule_detect_filenames"])
                self.submodule_text.insert("1.0", "\n".join(filenames))
            except:
                pass
                
    def create_setting_widget(self, parent, key, label, widget_type, options=None, description=None, readonly=False):
        """Create a setting widget"""
        frame = ctk.CTkFrame(parent)
        frame.pack(pady=10, padx=20, fill="x")
        
        # Label
        label_widget = ctk.CTkLabel(
            frame,
            text=label,
            font=ctk.CTkFont(size=12, weight="bold")
        )
        label_widget.pack(anchor="w")
        
        if description:
            desc_widget = ctk.CTkLabel(
                frame,
                text=description,
                font=ctk.CTkFont(size=10),
                text_color="gray"
            )
            desc_widget.pack(anchor="w")
            
        # Current value
        current_value = self.settings.get(key, "")
        
        # Create appropriate widget
        if widget_type == "dropdown":
            var = ctk.StringVar(value=current_value)
            widget = ctk.CTkOptionMenu(frame, values=options, variable=var)
            widget.pack(anchor="w", pady=5)
            self.setting_widgets[key] = var
            
        elif widget_type == "boolean":
            var = ctk.BooleanVar(value=current_value.lower() == "true")
            widget = ctk.CTkCheckBox(frame, text="Enabled", variable=var)
            widget.pack(anchor="w", pady=5)
            self.setting_widgets[key] = var
            
        elif widget_type == "number":
            var = ctk.StringVar(value=current_value)
            widget = ctk.CTkEntry(frame, textvariable=var)
            widget.pack(anchor="w", pady=5, fill="x")
            self.setting_widgets[key] = var
            
        else:  # text
            var = ctk.StringVar(value=current_value)
            widget = ctk.CTkEntry(frame, textvariable=var)
            if readonly:
                widget.configure(state="disabled")
            widget.pack(anchor="w", pady=5, fill="x")
            self.setting_widgets[key] = var
            
    def save_settings(self):
        """Save all settings"""
        saved_count = 0
        errors = []
        
        # Save each setting
        for key, widget in self.setting_widgets.items():
            try:
                if isinstance(widget, ctk.BooleanVar):
                    value = str(widget.get()).lower()
                else:
                    value = widget.get()
                    
                # Skip if value hasn't changed
                if self.settings.get(key, "") == value:
                    continue
                    
                # Save setting
                result = self.gui.run_csync_command(["config", "set", key, value])
                
                if result.returncode == 0:
                    saved_count += 1
                    self.settings[key] = value
                else:
                    errors.append(f"{key}: {result.stderr}")
                    
            except Exception as e:
                errors.append(f"{key}: {str(e)}")
                
        # Save submodule filenames
        try:
            filenames = self.submodule_text.get("1.0", "end").strip().split("\n")
            filenames = [f.strip() for f in filenames if f.strip()]
            if filenames:
                result = self.gui.run_csync_command([
                    "config", "set", "submodule_detect_filenames", 
                    json.dumps(filenames)
                ])
                if result.returncode == 0:
                    saved_count += 1
                else:
                    errors.append(f"submodule_detect_filenames: {result.stderr}")
        except Exception as e:
            errors.append(f"submodule_detect_filenames: {str(e)}")
            
        # Show result
        if errors:
            error_msg = "Some settings failed to save:\n" + "\n".join(errors[:5])
            if len(errors) > 5:
                error_msg += f"\n... and {len(errors) - 5} more"
            messagebox.showerror("Error", error_msg)
        elif saved_count > 0:
            messagebox.showinfo("Success", f"Saved {saved_count} settings successfully!")
        else:
            messagebox.showinfo("Info", "No settings were changed.")
