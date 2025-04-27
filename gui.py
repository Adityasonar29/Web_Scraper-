import platform
from urllib.parse import urlparse
import customtkinter as ctk
import threading
import os
import json
from PIL import Image, ImageTk, ImageOps, ImageDraw
import requests
from io import BytesIO
import webbrowser
import time
from tkinter import messagebox
import csv
import datetime
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib
matplotlib.use("TkAgg")
from collections import Counter, defaultdict
import pandas as pd
import shutil
import sqlite3
import re
import logging
import sys
import subprocess

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Custom logging handler to direct logs to the GUI
class GUILogHandler(logging.Handler):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        
    def emit(self, record):
        log_message = self.format(record)
        # Extract just the message part without timestamp
        if ']' in log_message and log_message.count(']') >= 2:
            message = log_message.split(']', 2)[2].strip()
        else:
            message = log_message
            
        # Schedule the callback in the main thread
        self.callback(message, record.levelname)

class WebScraperGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Set up logging
        self.setup_logging()
        
        # Basic window setup
        self.title("AI Web Scraper Pro")
        self.geometry("1280x720")
        self.minsize(1200, 700)
        
        # Initialize variables
        self.search_text = ctk.StringVar()
        self.current_results = []
        self.image_references = []
        self.search_history = []
        self.scrape_jobs = []
        self.notifications = []
        self.history_files = set()
        self.cancel_flag = False
        
        # Set up grid layout
        self.grid_columnconfigure(0, weight=0)  # Fixed sidebar
        self.grid_columnconfigure(1, weight=1)  # Expanding main content
        self.grid_rowconfigure(0, weight=1)
        
        # Set up theme colors
        self.colors = {
            "primary": "#1f6aa5",
            "secondary": "#4CAF50",
            "accent": "#ff9800",
            "success": "#4CAF50",
            "warning": "#ff9800",
            "error": "#f44336",
            "info": "#3b82f6",
            "dark_bg": "#1a1a1a",
            "card_bg": "#2b2b2b",
            "text": "#ffffff",
            "light": "#f3f4f6",
            "dark": "#1f2937"
        }
        
        # App settings
        self.settings = {
            "max_results": 50,
            "auto_save": True,
            "notifications": True,
            "thumbnail_size": 200,
            "default_exports_folder": "database/exports"
        }
        
        # Content type checkboxes will be created in create_filters
        self.content_types = {
            "images": ctk.BooleanVar(value=False),
            "videos": ctk.BooleanVar(value=False),
            "files": ctk.BooleanVar(value=False),
            "links": ctk.BooleanVar(value=False),
            "text": ctk.BooleanVar(value=False)
        }
        
        # Load settings
        self.load_settings()
        
        # Create interface components
        self.create_sidebar()
        self.create_main_content()
        self.create_status_bar()
        self.create_notification_area()
        
        # Set default tab
        self.tabs.set("📄 Current Results")
        
        # Load history
        self.refresh_history()
        
        # Ensure directories exist
        self.ensure_directories()
        
        # Update dashboard
        self.update_dashboard()
        
        # Show welcome notification
        self.add_notification("Welcome to AI Web Scraper Pro!", level="info")
        
        # Log application start
        self.log_message("Application started", "INFO")

    def setup_logging(self):
        """Configure logging to display in the GUI and save to files"""
        # Ensure log directory exists
        os.makedirs("database/logs", exist_ok=True)
        
        # Create timestamp for log file
        timestamp = datetime.datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
        log_file = os.path.join("database/logs", f"webscraper_log_{timestamp}.txt")
        
        # Create log handler that will update the GUI
        self.gui_log_handler = GUILogHandler(self.handle_log)
        self.gui_log_handler.setLevel(logging.INFO)
        self.gui_log_handler.setFormatter(
            logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', 
                             datefmt='%d-%m-%Y %H:%M:%S')
        )
        
        # Create file handler
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', 
                             datefmt='%d-%m-%Y %H:%M:%S')
        )
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        
        # Remove any existing handlers to avoid duplicates
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Add our handlers to the root logger
        root_logger.addHandler(self.gui_log_handler)
        root_logger.addHandler(file_handler)
        
        # Also add handlers for specific modules we use
        for logger_name in ['scrapy', 'twisted', 'webscraper_o2']:
            logger = logging.getLogger(logger_name)
            logger.addHandler(self.gui_log_handler)
            logger.addHandler(file_handler)
            
        logging.info(f"Logging initialized. Log file: {log_file}")

    def handle_log(self, message, level):
        """Handler to process logs from the custom handler"""
        self.log_message(message, level)

    def ensure_directories(self):
        """Ensure all required directories exist"""
        os.makedirs("database", exist_ok=True)
        os.makedirs("database/logs", exist_ok=True)
        os.makedirs("database/scraped_results", exist_ok=True)
        os.makedirs("database/cache", exist_ok=True)
        os.makedirs("database/files", exist_ok=True)
        os.makedirs(self.settings["default_exports_folder"], exist_ok=True)
        os.makedirs(os.path.join(self.settings["default_exports_folder"], "csv"), exist_ok=True)
        os.makedirs(os.path.join(self.settings["default_exports_folder"], "json"), exist_ok=True)
        
    def sanitize_filename(self, filename):
        """Sanitize a string to be used as a filename"""
        # Remove invalid characters for Windows filenames
        invalid_chars = r'<>:"/\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, "_")
        
        # Replace spaces with underscores
        filename = filename.replace(" ", "_")
        
        # Limit filename length
        if len(filename) > 100:
            filename = filename[:100]
            
        return filename
        
    def load_settings(self):
        """Load user settings from file if exists"""
        try:
            if os.path.exists("settings.json"):
                with open("settings.json", "r") as f:
                    saved_settings = json.load(f)
                    self.settings.update(saved_settings)
        except Exception as e:
            print(f"Error loading settings: {e}")
            
    def save_settings(self):
        """Save current settings to file"""
        try:
            with open("settings.json", "w") as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")
            self.add_notification("Failed to save settings", "error")

    def create_sidebar(self):
        """Create the sidebar with navigation and search elements"""
        # create sidebar frame with widgets
        self.sidebar_frame = ctk.CTkFrame(self, width=960, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=4, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(0, weight=1)
        self.sidebar_frame.grid_columnconfigure(0, weight=1)
        
        # Add a sidebar toggle button
        self.sidebar_expanded = True
        self.sidebar_toggle_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.sidebar_toggle_frame.grid(row=0, column=1, sticky="ne", padx=5, pady=5)
        
        self.sidebar_toggle_btn = ctk.CTkButton(
            self.sidebar_toggle_frame,
            text="◀",
            width=30,
            height=30,
            command=self.toggle_sidebar,
            font=("Arial", 14, "bold")
        )
        self.sidebar_toggle_btn.grid(row=0, column=0)
        
        # Add scrollable container
        self.sidebar = ctk.CTkScrollableFrame(self.sidebar_frame, fg_color="transparent")
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        
        # Logo and header
        self.logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.logo_frame.pack(pady=15, padx=15, fill="x")
        
        self.logo_label = ctk.CTkLabel(
            self.logo_frame,
            text="AI Web Scraper Pro",
            font=("Arial", 20, "bold")
        )
        self.logo_label.pack(side="left", padx=5)
        
        # Theme Switcher
        self.theme_switch = ctk.CTkSwitch(
            self.sidebar, 
            text="Dark Mode", 
            command=self.toggle_theme,
            font=("Arial", 14)
        )
        self.theme_switch.pack(pady=5, padx=15, anchor="w")
        if ctk.get_appearance_mode() == "Dark":
            self.theme_switch.select()
        
        # Navigation menu
        self.nav_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.nav_frame.pack(pady=15, padx=15, fill="x")
        
        self.nav_label = ctk.CTkLabel(
            self.nav_frame,
            text="NAVIGATION",
            font=("Arial", 12, "bold"),
            text_color="#aaaaaa"
        )
        self.nav_label.pack(anchor="w", pady=(0, 10))
        
        # Navigation buttons
        nav_buttons = [
            ("🔍 Search & Scrape", lambda: self.tabs.set("📄 Current Results")),
            ("📊 Dashboard", lambda: self.tabs.set("📊 Dashboard")),
            ("🕒 History", lambda: self.tabs.set("🕒 History")),
            ("📝 Logs", lambda: self.tabs.set("📝 Logs")),
            ("⚙️ Settings", lambda: self.tabs.set("⚙️ Settings")),
            ("❓ Help", lambda: self.tabs.set("❓ Help"))
        ]
        
        for text, command in nav_buttons:
            btn = ctk.CTkButton(
                self.nav_frame,
                text=text,
                command=command,
                anchor="w",
                height=40,
                fg_color="transparent",
                text_color=self.colors["text"],
                hover_color=self.colors["primary"],
                font=("Arial", 14)
            )
            btn.pack(fill="x", pady=5)
        
        # Search Section
        self.search_frame = ctk.CTkFrame(self.sidebar)
        self.search_frame.pack(pady=15, padx=15, fill="x")
        
        self.search_label = ctk.CTkLabel(
            self.search_frame,
            text="SEARCH",
            font=("Arial", 12, "bold"),
            text_color="#aaaaaa"
        )
        self.search_label.pack(anchor="w", pady=(0, 10))
        
        self.search_entry = ctk.CTkEntry(
            self.search_frame, 
            placeholder_text="🔍 Enter search query...",
            height=40,
            font=("Arial", 14))
        self.search_entry.pack(pady=8, fill="x")
        
        # Remove search type selector and replace with buttons
        self.search_buttons_frame = ctk.CTkFrame(self.search_frame, fg_color="transparent")
        self.search_buttons_frame.pack(fill="x", pady=5)
        
        # Web scraping button (existing)
        self.scrape_btn = ctk.CTkButton(
            self.search_buttons_frame, 
            text="🚀 Scrape Web", 
            command=self.start_scraping_thread,
            hover_color="#2d8cff",
            height=45,
            font=("Arial", 14, "bold"))
        self.scrape_btn.pack(pady=8, fill="x")
        
        # Database search button (new)
        self.db_search_btn = ctk.CTkButton(
            self.search_buttons_frame, 
            text="🔍 Search Database", 
            command=self.search_database,
            fg_color=self.colors["secondary"],
            hover_color="#45a049",
            height=45,
            font=("Arial", 14, "bold"))
        self.db_search_btn.pack(pady=8, fill="x")
        
        # Batch scrape button
        self.batch_btn = ctk.CTkButton(
            self.search_frame, 
            text="📚 Batch Processing", 
            command=self.show_batch_processing,
            fg_color=self.colors["accent"],
            hover_color="#e68a00",
            height=40,
            font=("Arial", 14))
        self.batch_btn.pack(pady=8, fill="x")

        # letest scrape result see button        
        ctk.CTkButton(
            self.sidebar,
            text="📂 Open Latest Scrape File",
            command=self.open_latest_scrape_file,
            fg_color="#607d8b",
            hover_color="#455a64",
            height=40,
            font=("Arial", 14)
        ).pack(pady=5, padx=15, fill="x")

        
        # Filters Section
        self.create_filters()
        
        # Export Button
        self.export_btn = ctk.CTkButton(
            self.sidebar,
            text="💾 Export Results",
            command=self.export_results,
            fg_color=self.colors["secondary"],
            hover_color="#45a049",
            height=45,
            font=("Arial", 14))
        self.export_btn.pack(pady=15, padx=15, fill="x")
        
        # Refresh Button
        self.refresh_btn = ctk.CTkButton(
            self.sidebar,
            text="🔄 Refresh All",
            command=self.refresh_application,
            fg_color=self.colors["primary"],
            hover_color="#2d8cff",
            height=40,
            font=("Arial", 14))
        self.refresh_btn.pack(pady=5, padx=15, fill="x")
        
        # Downloadable Files Button
        self.files_btn = ctk.CTkButton(
            self.sidebar,
            text="⬇️ Downloadable Files",
            command=self.show_downloadable_files,
            fg_color=self.colors["accent"],
            hover_color="#e68a00",
            height=40,
            font=("Arial", 14))
        self.files_btn.pack(pady=5, padx=15, fill="x")
        
        # Cache Management Button
        self.cache_btn = ctk.CTkButton(
            self.sidebar,
            text="🗄️ Manage Cache",
            command=self.manage_cache,
            fg_color="#607d8b",  # Blue-grey color
            hover_color="#455a64",
            height=40,
            font=("Arial", 14))
        self.cache_btn.pack(pady=5, padx=15, fill="x")
        
        # Version info
        self.version_label = ctk.CTkLabel(
            self.sidebar,
            text="v2.0.0",
            font=("Arial", 10),
            text_color="#aaaaaa"
        )
        self.version_label.pack(pady=10)

    def create_filters(self):
        self.filter_frame = ctk.CTkFrame(self.sidebar)
        self.filter_frame.pack(pady=15, padx=15, fill="x")
        
        self.filter_label = ctk.CTkLabel(
            self.filter_frame,
            text="FILTERS",
            font=("Arial", 12, "bold"),
            text_color="#aaaaaa"
        )
        self.filter_label.pack(anchor="w", pady=(0, 10))
        
        # Filter tabs
        self.filter_tabs = ctk.CTkTabview(self.filter_frame, height=280)
        self.filter_tabs.pack(fill="x")
        
        # Content tab
        content_tab = self.filter_tabs.add("Content")
        
        # Content Type Filters
        self.content_types = {
            "images": ctk.CTkCheckBox(content_tab, text="🖼 Images", font=("Arial", 14)),
            "videos": ctk.CTkCheckBox(content_tab, text="🎥 Videos", font=("Arial", 14)),
            "files": ctk.CTkCheckBox(content_tab, text="📁 Files", font=("Arial", 14)),
            "links": ctk.CTkCheckBox(content_tab, text="🔗 Links", font=("Arial", 14)),
            "text": ctk.CTkCheckBox(content_tab, text="📝 Text", font=("Arial", 14))
        }
        
        for cb in self.content_types.values():
            cb.pack(anchor="w", pady=4)
        
        # Source tab
        source_tab = self.filter_tabs.add("Source")
        
        # Domain Filter
        ctk.CTkLabel(source_tab, text="Domain Filter:", font=("Arial", 14)).pack(anchor="w", pady=(5, 0))
        self.domain_filter = ctk.CTkEntry(
            source_tab, 
            placeholder_text="🌐 e.g., example.com",
            font=("Arial", 14))
        self.domain_filter.pack(pady=5, fill="x")
        
        # Date range
        ctk.CTkLabel(source_tab, text="Date Range:", font=("Arial", 14)).pack(anchor="w", pady=(10, 0))
        
        date_frame = ctk.CTkFrame(source_tab, fg_color="transparent")
        date_frame.pack(fill="x", pady=5)
        
        self.date_options = ctk.CTkOptionMenu(
            date_frame,
            values=["Any Time", "Past 24 Hours", "Past Week", "Past Month", "Past Year", "Custom"],
            font=("Arial", 12),
            dropdown_font=("Arial", 12)
        )
        self.date_options.pack(fill="x")
        
        # Advanced tab
        advanced_tab = self.filter_tabs.add("Advanced")
        
        # Result Limit
        ctk.CTkLabel(advanced_tab, text="Max Results:", font=("Arial", 14)).pack(anchor="w", pady=(5, 0))
        self.limit_entry = ctk.CTkEntry(
            advanced_tab,
            placeholder_text="🔢 Default: 10",
            font=("Arial", 14))
        self.limit_entry.pack(pady=5, fill="x")
        
        # Language filter
        ctk.CTkLabel(advanced_tab, text="Language:", font=("Arial", 14)).pack(anchor="w", pady=(10, 0))
        self.language_option = ctk.CTkOptionMenu(
            advanced_tab,
            values=["Any", "English", "Spanish", "French", "German", "Chinese", "Japanese"],
            font=("Arial", 12),
            dropdown_font=("Arial", 12)
        )
        self.language_option.pack(fill="x", pady=5)
        
        # Search depth
        ctk.CTkLabel(advanced_tab, text="Search Depth:", font=("Arial", 14)).pack(anchor="w", pady=(10, 0))
        
        self.depth_slider = ctk.CTkSlider(
            advanced_tab,
            from_=1,
            to=5,
            number_of_steps=4
        )
        self.depth_slider.pack(fill="x", pady=5)
        self.depth_slider.set(2)
        
        self.depth_value_label = ctk.CTkLabel(advanced_tab, text="2", font=("Arial", 14))
        self.depth_value_label.pack()
        
        # Connect slider to label
        self.depth_slider.configure(command=self.update_depth_label)
        
        # Save filter preset button
        save_preset_btn = ctk.CTkButton(
            self.filter_frame,
            text="💾 Save Filter Preset",
            command=self.save_filter_preset,
            fg_color=self.colors["primary"],
            font=("Arial", 12)
        )
        save_preset_btn.pack(fill="x", pady=10)
        
    def update_depth_label(self, value):
        """Update the depth label when slider changes"""
        depth = int(value)
        self.depth_value_label.configure(text=str(depth))
        
    def save_filter_preset(self):
        """Save current filter settings as a preset"""
        preset_name = ctk.CTkInputDialog(
            text="Enter preset name:",
            title="Save Filter Preset"
        ).get_input()
        
        if preset_name:
            # Save current filter configuration
            preset = {
                "content_types": {k: v.get() for k, v in self.content_types.items()},
                "domain": self.domain_filter.get(),
                "date_range": self.date_options.get(),
                "limit": self.limit_entry.get() or self.settings["max_results"],
                "language": self.language_option.get(),
                "depth": int(self.depth_slider.get())
            }
            
            # Load existing presets
            presets = {}
            if os.path.exists("database/filter_presets.json"):
                with open("database/filter_presets.json", "r") as f:
                    presets = json.load(f)
                    
            # Add new preset
            presets[preset_name] = preset
            
            # Save to file
            with open("filter_presets.json", "w") as f:
                json.dump(presets, f, indent=2)
                
            self.add_notification(f"Filter preset '{preset_name}' saved", "success")

    def create_main_content(self):
        self.tabs = ctk.CTkTabview(self, segmented_button_selected_color=self.colors["primary"])
        self.tabs.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        
        # Current Results Tab
        self.results_tab = self.tabs.add("📄 Current Results")
        self.results_tab.grid_columnconfigure(0, weight=1)
        self.results_tab.grid_rowconfigure(0, weight=1)
        
        self.search_controls_frame = ctk.CTkFrame(self.results_tab)
        self.search_controls_frame.pack(fill="x", pady=(0, 10))
        
        # Search controls
        self.view_toggle_var = ctk.StringVar(value="List")
        view_options = ctk.CTkSegmentedButton(
            self.search_controls_frame,
            values=["List", "Grid", "Cards"],
            variable=self.view_toggle_var,
            command=self.toggle_view_mode
        )
        view_options.pack(side="left", padx=10)
        
        # Sort options
        sort_label = ctk.CTkLabel(self.search_controls_frame, text="Sort by:", font=("Arial", 12))
        sort_label.pack(side="left", padx=(20, 5))
        
        self.sort_option = ctk.CTkOptionMenu(
            self.search_controls_frame,
            values=["Relevance", "Date", "Title", "Domain"],
            width=120,
            font=("Arial", 12),
            dropdown_font=("Arial", 12)
        )
        self.sort_option.pack(side="left", padx=5)
        
        # Search statistics
        self.stats_label = ctk.CTkLabel(
            self.search_controls_frame,
            text="Found: 0 results",
            font=("Arial", 12)
        )
        self.stats_label.pack(side="right", padx=10)
        
        # Results area
        self.results_canvas = ctk.CTkScrollableFrame(self.results_tab)
        self.results_canvas.pack(fill="both", expand=True)
        
        # Dashboard Tab with analytics
        self.dashboard_tab = self.tabs.add("📊 Dashboard")
        self.dashboard_tab.grid_columnconfigure(0, weight=1)
        self.dashboard_tab.grid_rowconfigure(0, weight=1)
        
        self.create_dashboard()
        
        # History Tab
        self.history_tab = self.tabs.add("🕒 History")
        self.history_tab.grid_columnconfigure(0, weight=1)
        self.history_tab.grid_rowconfigure(0, weight=1)
        
        self.history_frame = ctk.CTkFrame(self.history_tab)
        self.history_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.history_header = ctk.CTkFrame(self.history_frame)
        self.history_header.pack(fill="x", pady=10)
        
        self.history_title = ctk.CTkLabel(
            self.history_header,
            text="Search History",
            font=("Arial", 18, "bold")
        )
        self.history_title.pack(side="left", padx=10)
        
        self.clear_history_btn = ctk.CTkButton(
            self.history_header,
            text="🗑️ Clear History",
            command=self.clear_history,
            fg_color=self.colors["error"],
            hover_color="#d32f2f",
            width=120,
            font=("Arial", 12)
        )
        self.clear_history_btn.pack(side="right", padx=10)
        
        self.history_list = ctk.CTkScrollableFrame(self.history_frame)
        self.history_list.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Log Viewer Tab
        self.logs_tab = self.tabs.add("📝 Logs")
        self.logs_tab.grid_columnconfigure(0, weight=1)
        self.logs_tab.grid_rowconfigure(0, weight=1)
        
        self.logs_frame = ctk.CTkFrame(self.logs_tab)
        self.logs_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.logs_header = ctk.CTkFrame(self.logs_frame)
        self.logs_header.pack(fill="x", pady=10)
        
        self.logs_title = ctk.CTkLabel(
            self.logs_header,
            text="Application Logs",
            font=("Arial", 18, "bold")
        )
        self.logs_title.pack(side="left", padx=10)
        
        self.clear_logs_btn = ctk.CTkButton(
            self.logs_header,
            text="🗑️ Clear Logs",
            command=self.clear_logs,
            fg_color=self.colors["error"],
            hover_color="#d32f2f",
            width=120,
            font=("Arial", 12)
        )
        self.clear_logs_btn.pack(side="right", padx=10)
        
        self.logs_text = ctk.CTkTextbox(self.logs_frame, font=("Consolas", 12))
        self.logs_text.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Settings Tab
        self.settings_tab = self.tabs.add("⚙️ Settings")
        self.create_settings_tab()
        
        # Help Tab
        self.help_tab = self.tabs.add("❓ Help")
        self.create_help_tab()

    def toggle_view_mode(self, mode):
        """Toggle between different result view modes"""
        self.clear_results()
        
        if self.current_results:
            for result in self.current_results:
                self.display_result(result)
            
    def clear_logs(self):
        """Clear the logs display"""
        self.logs_text.delete("1.0", "end")
        self.log_message("Logs cleared")
        
    def log_message(self, message, level="INFO"):
        """Add a message to the logs with timestamp and level"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        level_colors = {
            "INFO": "#4caf50",
            "WARNING": "#ff9800",
            "ERROR": "#f44336",
            "DEBUG": "#2196f3"
        }
        level_color = level_colors.get(level.upper(), "#ffffff")
        
        # Only create log if the text widget exists
        if hasattr(self, 'logs_text'):
            self.logs_text.insert("end", f"[{timestamp}] ", "timestamp")
            self.logs_text.insert("end", f"[{level.upper()}] ", level.upper())
            self.logs_text.insert("end", f"{message}\n", "message")
            
            # Configure tags for colorization
            self.logs_text.tag_config("timestamp", foreground="#aaaaaa")
            self.logs_text.tag_config("INFO", foreground="#4caf50")
            self.logs_text.tag_config("WARNING", foreground="#ff9800")
            self.logs_text.tag_config("ERROR", foreground="#f44336")
            self.logs_text.tag_config("DEBUG", foreground="#2196f3")
            
            # Scroll to the bottom
            self.logs_text.see("end")
            
        # Also print to console for debugging
        print(f"[{timestamp}] [{level.upper()}] {message}")

    def create_dashboard(self):
        """Create dashboard with analytics"""
        self.dashboard_frame = ctk.CTkFrame(self.dashboard_tab)
        self.dashboard_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Stats cards row
        self.stats_frame = ctk.CTkFrame(self.dashboard_frame)
        self.stats_frame.pack(fill="x", pady=10, padx=10)
        
        # Create stat cards
        self.stat_cards = []
        
        stat_data = [
            {"title": "Total Scrapes", "value": "0", "icon": "🔍", "color": self.colors["primary"]},
            {"title": "Pages Indexed", "value": "0", "icon": "📑", "color": self.colors["secondary"]},
            {"title": "Media Files", "value": "0", "icon": "🖼️", "color": self.colors["accent"]},
            {"title": "Search Time", "value": "0s", "icon": "⏱️", "color": "#9c27b0"}
        ]
        
        for data in stat_data:
            card = self.create_stat_card(self.stats_frame, data)
            card.pack(side="left", fill="both", expand=True, padx=5)
            self.stat_cards.append(card)
            
        # Charts section
        self.charts_frame = ctk.CTkFrame(self.dashboard_frame)
        self.charts_frame.pack(fill="both", expand=True, pady=10, padx=10)
        
        # Configure grid for charts
        self.charts_frame.grid_columnconfigure(0, weight=1)
        self.charts_frame.grid_columnconfigure(1, weight=1)
        self.charts_frame.grid_rowconfigure(0, weight=1)
        self.charts_frame.grid_rowconfigure(1, weight=1)
        
        # Placeholder for charts - will be populated in update_dashboard
        self.chart_frames = []
        
        chart_titles = [
            "Content Types Distribution", 
            "Top Domains", 
            "Scraping History", 
            "File Types Distribution"
        ]
        
        for i, title in enumerate(chart_titles):
            row, col = divmod(i, 2)
            frame = ctk.CTkFrame(self.charts_frame)
            frame.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)
            
            header = ctk.CTkLabel(frame, text=title, font=("Arial", 16, "bold"))
            header.pack(pady=10)
            
            chart_area = ctk.CTkFrame(frame, fg_color="transparent")
            chart_area.pack(fill="both", expand=True, padx=10, pady=10)
            
            self.chart_frames.append({"frame": frame, "title": title, "area": chart_area})
    
    def create_stat_card(self, parent, data):
        """Create a statistics card for dashboard"""
        card = ctk.CTkFrame(parent, corner_radius=10, height=100)
        
        icon_label = ctk.CTkLabel(
            card, 
            text=data["icon"],
            font=("Arial", 24),
            text_color=data["color"]
        )
        icon_label.pack(side="left", padx=(15, 5))
        
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, pady=10)
        
        title_label = ctk.CTkLabel(
            info_frame,
            text=data["title"],
            font=("Arial", 12),
            anchor="w"
        )
        title_label.pack(anchor="w")
        
        value_label = ctk.CTkLabel(
            info_frame,
            text=data["value"],
            font=("Arial", 20, "bold"),
            text_color=data["color"],
            anchor="w"
        )
        value_label.pack(anchor="w")
        
        return card
        
    def create_settings_tab(self):
        """Create settings tab with user preferences"""
        self.settings_frame = ctk.CTkFrame(self.settings_tab)
        self.settings_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Settings header
        settings_header = ctk.CTkLabel(
            self.settings_frame,
            text="Application Settings",
            font=("Arial", 20, "bold")
        )
        settings_header.pack(anchor="w", pady=(0, 20))
        
        # Settings sections
        sections = [
            {
                "title": "General Settings",
                "settings": [
                    {
                        "type": "switch",
                        "text": "Enable Notifications",
                        "variable": "notifications",
                        "default": True
                    },
                    {
                        "type": "switch",
                        "text": "Auto-save Results",
                        "variable": "auto_save",
                        "default": True
                    },
                    {
                        "type": "entry",
                        "text": "Default Exports Folder:",
                        "variable": "default_exports_folder",
                        "default": "database/exports"
                    }
                ]
            },
            {
                "title": "Scraping Settings",
                "settings": [
                    {
                        "type": "entry",
                        "text": "Maximum Results per Search:",
                        "variable": "max_results",
                        "default": "50"
                    },
                    {
                        "type": "slider",
                        "text": "Thumbnail Size:",
                        "variable": "thumbnail_size",
                        "default": 200,
                        "min": 100,
                        "max": 300,
                        "step": 50
                    },
                    {
                        "type": "switch",
                        "text": "Use System Proxy",
                        "variable": "use_proxy",
                        "default": False
                    }
                ]
            },
            {
                "title": "Database Management",
                "settings": [
                    {
                        "type": "button",
                        "text": "Clear Database Cache",
                        "command": self.clear_database_cache,
                        "color": self.colors["warning"]
                    },
                    {
                        "type": "button",
                        "text": "Export Database",
                        "command": self.export_database,
                        "color": self.colors["primary"]
                    },
                    {
                        "type": "button",
                        "text": "Import Database",
                        "command": self.import_database,
                        "color": self.colors["primary"]
                    }
                ]
            }
        ]
        
        # Create settings controls
        self.settings_controls = {}
        
        for section in sections:
            # Section frame
            section_frame = ctk.CTkFrame(self.settings_frame)
            section_frame.pack(fill="x", pady=10)
            
            # Section header
            section_label = ctk.CTkLabel(
                section_frame,
                text=section["title"],
                font=("Arial", 16, "bold")
            )
            section_label.pack(anchor="w", padx=15, pady=10)
            
            # Settings
            for setting in section["settings"]:
                setting_frame = ctk.CTkFrame(section_frame, fg_color="transparent")
                setting_frame.pack(fill="x", padx=25, pady=5)
                
                if "text" in setting:
                    label = ctk.CTkLabel(setting_frame, text=setting["text"], font=("Arial", 14))
                    label.pack(side="left", padx=5)
                
                if setting["type"] == "switch":
                    control = ctk.CTkSwitch(setting_frame, text="")
                    if self.settings.get(setting["variable"], setting["default"]):
                        control.select()
                    control.pack(side="right", padx=5)
                    self.settings_controls[setting["variable"]] = control
                    
                elif setting["type"] == "entry":
                    control = ctk.CTkEntry(setting_frame, width=200)
                    control.insert(0, str(self.settings.get(setting["variable"], setting["default"])))
                    control.pack(side="right", padx=5)
                    self.settings_controls[setting["variable"]] = control
                    
                elif setting["type"] == "slider":
                    slider_frame = ctk.CTkFrame(setting_frame, fg_color="transparent")
                    slider_frame.pack(side="right", padx=5, fill="x", expand=True)
                    
                    control = ctk.CTkSlider(
                        slider_frame,
                        from_=setting["min"],
                        to=setting["max"],
                        number_of_steps=int((setting["max"] - setting["min"]) / setting["step"])
                    )
                    control.pack(side="left", fill="x", expand=True)
                    control.set(self.settings.get(setting["variable"], setting["default"]))
                    
                    value_label = ctk.CTkLabel(slider_frame, text=str(int(control.get())))
                    value_label.pack(side="right", padx=10)
                    
                    # Update label when slider changes
                    control.configure(command=lambda v, label=value_label: label.configure(text=str(int(v))))
                    
                    self.settings_controls[setting["variable"]] = control
                    
                elif setting["type"] == "button":
                    control = ctk.CTkButton(
                        setting_frame,
                        text=setting["text"],
                        command=setting["command"],
                        fg_color=setting["color"],
                        width=200
                    )
                    control.pack(side="right", padx=5)
        
        # Save settings button
        save_btn = ctk.CTkButton(
            self.settings_frame,
            text="Save Settings",
            command=self.apply_settings,
            fg_color=self.colors["success"],
            font=("Arial", 14)
        )
        save_btn.pack(pady=20)
    
    def create_help_tab(self):
        """Create help/documentation tab"""
        self.help_frame = ctk.CTkFrame(self.help_tab)
        self.help_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Help header
        help_header = ctk.CTkLabel(
            self.help_frame,
            text="Help & Documentation",
            font=("Arial", 20, "bold")
        )
        help_header.pack(anchor="w", pady=(0, 20))
        
        # Create tabs for different help sections
        help_tabs = ctk.CTkTabview(self.help_frame)
        help_tabs.pack(fill="both", expand=True)
        
        # Getting Started tab
        getting_started = help_tabs.add("Getting Started")
        self.create_help_section(
            getting_started,
            "Welcome to AI Web Scraper Pro!",
            [
                "This application helps you search and scrape content from the web.",
                "To get started, simply enter a search query in the sidebar and click 'Start Scraping'.",
                "You can use filters to narrow down your search results.",
                "Results will appear in the 'Current Results' tab and can be exported."
            ]
        )
        
        # Features tab
        features = help_tabs.add("Features")
        self.create_help_section(
            features,
            "Key Features",
            [
                "🔍 Intelligent Web Scraping - Search and extract content from websites",
                "🖼️ Media Extraction - Find images, videos, and files",
                "📊 Analytics Dashboard - Visual insights about your scraping activities",
                "💾 Export Options - Save results in various formats (CSV, JSON)",
                "🔄 Batch Processing - Run multiple searches at once",
                "📱 Responsive UI - Customizable interface with light and dark modes"
            ]
        )
        
        # Tips tab
        tips = help_tabs.add("Tips & Tricks")
        self.create_help_section(
            tips,
            "Tips for Effective Scraping",
            [
                "Use specific search queries for better results",
                "Apply filters to narrow down your search",
                "Save filter presets for commonly used configurations",
                "Use the dashboard to analyze trends in your data",
                "Export your results regularly to avoid data loss",
                "Check the search history to revisit previous queries"
            ]
        )
        
        # About tab
        about = help_tabs.add("About")
        self.create_help_section(
            about,
            "About AI Web Scraper Pro",
            [
                "Version: 2.0.0",
                "Built with: Python, CustomTkinter",
                "License: MIT",
                "For more information, visit our GitHub repository."
            ]
        )
        
        # Create contact section with email button
        contact_frame = ctk.CTkFrame(about)
        contact_frame.pack(fill="x", pady=20)
        
        ctk.CTkLabel(
            contact_frame,
            text="Need help or have suggestions?",
            font=("Arial", 14, "bold")
        ).pack(pady=10)
        
        ctk.CTkButton(
            contact_frame,
            text="📧 Contact Support",
            command=lambda: webbrowser.open("mailto:support@example.com"),
            fg_color=self.colors["primary"]
        ).pack(pady=10)
        
    def create_help_section(self, parent, title, bullet_points):
        """Create a help section with title and bullet points"""
        frame = ctk.CTkFrame(parent)
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(
            frame,
            text=title,
            font=("Arial", 18, "bold")
        ).pack(anchor="w", pady=10)
        
        for point in bullet_points:
            ctk.CTkLabel(
                frame,
                text=point,
                font=("Arial", 14),
                anchor="w",
                justify="left"
            ).pack(anchor="w", pady=5, padx=20)

    def create_status_bar(self):
        self.status_bar = ctk.CTkFrame(self, height=40)
        self.status_bar.grid(row=1, column=1, sticky="ew")
        
        self.status_label = ctk.CTkLabel(
            self.status_bar, 
            text="✅ Ready",
            anchor="w",
            font=("Arial", 13))
        self.status_label.pack(side="left", padx=15)
        
        # Add stats to status bar
        self.status_stats_frame = ctk.CTkFrame(self.status_bar, fg_color="transparent")
        self.status_stats_frame.pack(side="left", padx=20)
        
        self.pages_label = ctk.CTkLabel(
            self.status_stats_frame,
            text="Pages: 0",
            font=("Arial", 12)
        )
        self.pages_label.pack(side="left", padx=10)
        
        self.items_label = ctk.CTkLabel(
            self.status_stats_frame,
            text="Items: 0",
            font=("Arial", 12)
        )
        self.items_label.pack(side="left", padx=10)
        
        self.time_label = ctk.CTkLabel(
            self.status_stats_frame,
            text="Time: 0.0s",
            font=("Arial", 12)
        )
        self.time_label.pack(side="left", padx=10)
        
        # Progress indicator
        self.progress_frame = ctk.CTkFrame(self.status_bar, fg_color="transparent")
        self.progress_frame.pack(side="right", padx=15)
        
        self.progress = ctk.CTkProgressBar(self.progress_frame, width=200)
        self.progress.pack(side="right")
        self.progress.set(0)
        
        # Cancel button (hidden by default)
        self.cancel_btn = ctk.CTkButton(
            self.progress_frame,
            text="Cancel",
            width=80,
            fg_color=self.colors["error"],
            command=self.cancel_operation
        )
        
    def create_notification_area(self):
        """Create a notification area for toast messages"""
        # Create a completely transparent frame
        self.notification_area = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        
        # Place dynamically in the top-right corner of the content area
        self.notification_area.place(relx=0.98, rely=0.05, anchor="ne")
        
        # Ensure the notification area is visible and above other elements
        self.notification_area.lift()
        
        # Initialize list of notifications and ensure it's empty
        self.notifications = []
        
    def add_notification(self, message, level="info", duration=3000):
        """Add a notification toast message"""
        if not self.settings.get("notifications", True):
            return
            
        # Define colors for different notification levels
        colors = {
            "info": self.colors["primary"],
            "success": self.colors["success"],
            "warning": self.colors["warning"],
            "error": self.colors["error"]
        }
        
        # Create notification frame
        notification = ctk.CTkFrame(self.notification_area, corner_radius=10, fg_color=colors.get(level, colors["info"]))
        notification.pack(pady=5, fill="x")
        
        # Add icon based on level
        icons = {
            "info": "ℹ️",
            "success": "✅",
            "warning": "⚠️",
            "error": "❌"
        }
        
        content = ctk.CTkFrame(notification, fg_color="transparent")
        content.pack(padx=15, pady=10, fill="x")
        
        icon_label = ctk.CTkLabel(content, text=icons.get(level, "ℹ️"), font=("Arial", 14))
        icon_label.pack(side="left", padx=(0, 10))
        
        text_label = ctk.CTkLabel(content, text=message, font=("Arial", 13))
        text_label.pack(side="left", fill="x", expand=True)
        
        close_btn = ctk.CTkButton(
            content,
            text="×",
            width=20,
            height=20,
            command=lambda: self.remove_notification(notification),  # Use the method not direct destroy
            fg_color="transparent",
            hover_color="#e0e0e0",
            font=("Arial", 16)
        )
        close_btn.pack(side="right")
        
        # Store notification in list
        self.notifications.append(notification)
        
        # Auto-remove after duration
        self.after(duration, lambda: self.remove_notification(notification))
        
        return notification
        
    def remove_notification(self, notification):
        """Remove a notification if it still exists"""
        try:
            if notification in self.notifications:
                # First remove from list
                self.notifications.remove(notification)
                
                # Then destroy the widget if it exists
                if notification.winfo_exists():
                    notification.destroy()
                
                # Force update to prevent graphical glitches
                self.notification_area.update_idletasks()
                
                # If this was the last notification, refresh the notification area
                if len(self.notifications) == 0:
                    # Hide and show the notification area to clear any artifacts
                    self.notification_area.place_forget()
                    self.after(50, lambda: self.notification_area.place(relx=0.98, rely=0.05, anchor="ne"))
        except Exception as e:
            # Log error but don't crash
            print(f"Error removing notification: {str(e)}")
            
            # Try direct destroy as fallback
            try:
                if notification.winfo_exists():
                    notification.destroy()
            except:
                pass
    
    def cancel_operation(self):
        """Cancel the current operation"""
        # Set a flag to stop any ongoing operations
        self.cancel_flag = True
        self.update_status("🛑 Operation cancelled")
        self.cancel_btn.pack_forget()
        self.progress.set(0)

    def toggle_theme(self):
        current = ctk.get_appearance_mode()
        new_mode = "Dark" if current == "Light" else "Light"
        ctk.set_appearance_mode(new_mode)
        self.theme_switch.configure(text=f"{new_mode} Mode")

    def refresh_application(self):
        """Completely refresh the application state"""
        try:
            # Clear current results
            self.clear_results()
            
            # Refresh history
            self.refresh_history()
            
            # Update dashboard with fresh statistics
            self.update_dashboard()
            
            # Clear logs display
            self.clear_logs()
            
            # Refresh database connection
            self.reconnect_database()
            
            # Update status
            self.update_status("✅ Application refreshed!")
            self.add_notification("All data refreshed successfully", "success")
        except Exception as e:
            self.log_message(f"Error refreshing application: {str(e)}", "ERROR")
            self.add_notification(f"Error during refresh: {str(e)}", "error")
    
    def reconnect_database(self):
        """Reconnect to the database to ensure fresh connection"""
        try:
            # Import database module
            from webscraper_o2 import query_database
            
            # Run a simple query to test connection
            results = query_database(limit=1)
            
            if results:
                self.log_message("Database connection refreshed successfully", "INFO")
            else:
                self.log_message("Database connection refreshed (no results)", "INFO")
        except Exception as e:
            self.log_message(f"Error reconnecting to database: {str(e)}", "ERROR")
            raise e

    def create_thumbnail(self, url, size=(200, 200)):
        try:
            response = requests.get(url, timeout=5)
            img = Image.open(BytesIO(response.content))
            img = ImageOps.fit(img, size, Image.LANCZOS)
            return ImageTk.PhotoImage(img)
        except Exception as e:
            return self.create_placeholder_image(f"⚠️ Image Error", size)

    def create_placeholder_image(self, text, size=(200, 200)):
        img = Image.new("RGB", size, "#2b2b2b")
        draw = ImageDraw.Draw(img)
        draw.text((10, 80), text, fill="white")
        return ImageTk.PhotoImage(img)

    def display_result(self, result):
        view_mode = self.view_toggle_var.get()
        
        if view_mode == "List":
            self._display_result_list(result)
        elif view_mode == "Grid":
            self._display_result_grid(result)
        else:  # Cards
            self._display_result_card(result)
    
    def _display_result_list(self, result):
        """Display result in list view (compact)"""
        result_frame = ctk.CTkFrame(self.results_canvas, corner_radius=10)
        result_frame.pack(fill="x", pady=5, padx=5)
        
        # Main content
        main_frame = ctk.CTkFrame(result_frame, fg_color="transparent")
        main_frame.pack(fill="x", padx=10, pady=10)
        
        # Try to get first image for thumbnail
        thumbnail_frame = ctk.CTkFrame(main_frame, width=80, height=80, fg_color="transparent")
        thumbnail_frame.pack(side="left", padx=(0, 15))
        
        # Get first image if available
        images = json.loads(result['images'])
        if images:
            try:
                thumbnail = self.create_thumbnail(images[0]['src'])
                if thumbnail:
                    img_label = ctk.CTkLabel(thumbnail_frame, image=thumbnail, text="")
                    img_label.image = thumbnail
                    self.image_references.append(thumbnail)
                    img_label.pack(fill="both", expand=True)
            except Exception:
                # Fallback icon if image fails
                ctk.CTkLabel(thumbnail_frame, text="🌐", font=("Arial", 30)).pack(pady=20)
        else:
            # No image available
            ctk.CTkLabel(thumbnail_frame, text="🌐", font=("Arial", 30)).pack(pady=20)
        
        # Text content
        text_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        text_frame.pack(side="left", fill="both", expand=True)
        
        # Title with "open in browser" icon button
        title_frame = ctk.CTkFrame(text_frame, fg_color="transparent")
        title_frame.pack(fill="x")
        
        title_label = ctk.CTkLabel(
            title_frame, 
            text=result['title'], 
            font=("Arial", 16, "bold"),
            anchor="w")
        title_label.pack(side="left", fill="x", expand=True)
        
        # URL label
        url_label = ctk.CTkLabel(
            text_frame,
            text=result['url'],
            font=("Arial", 12),
            text_color="gray",
            anchor="w"
        )
        url_label.pack(anchor="w", pady=(2, 5))
        
        # Text preview
        text_preview = result['body_content'][:200] + "..." if len(result['body_content']) > 200 else result['body_content']
        preview_label = ctk.CTkLabel(
            text_frame, 
            text=text_preview, 
            wraplength=800,
            font=("Arial", 13),
            anchor="w",
            justify="left")
        preview_label.pack(anchor="w", fill="x")
        
        # Bottom info bar
        info_frame = ctk.CTkFrame(result_frame, fg_color=self.colors["card_bg"])
        info_frame.pack(fill="x")
        
        # Metadata items
        metadata_items = [
            f"🔗 {urlparse(result['url']).netloc}",
            f"🕒 {result['timestamp']}",
            f"🖼️ {len(json.loads(result['images']))}",
            f"🎥 {len(json.loads(result['videos']))}",
            f"📁 {len(json.loads(result['files']))}"
        ]
        
        for item in metadata_items:
            ctk.CTkLabel(
                info_frame,
                text=item,
                font=("Arial", 12),
                padx=5
            ).pack(side="left", padx=5)
        
        # Action buttons
        action_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
        action_frame.pack(side="right")
        
        # Open button
        open_btn = ctk.CTkButton(
            action_frame,
            text="Open",
            command=lambda url=result['url']: webbrowser.open(url),
            width=70,
            height=24,
            font=("Arial", 12)
        )
        open_btn.pack(side="left", padx=(0, 5))
        
        # Save button
        save_btn = ctk.CTkButton(
            action_frame,
            text="Save",
            command=lambda r=result: self.save_single_result(r),
            width=70,
            height=24,
            fg_color=self.colors["secondary"],
            font=("Arial", 12)
        )
        save_btn.pack(side="left", padx=5)
    
    def _display_result_grid(self, result):
        """Display result in grid view (image-focused)"""
        # Create a frame for this grid item - set fixed width for grid layout
        if not hasattr(self, 'grid_container'):
            # Create a container for the grid layout
            self.grid_container = ctk.CTkFrame(self.results_canvas, fg_color="transparent")
            self.grid_container.pack(fill="both", expand=True)
            
            # Initialize rows for grid layout
            self.current_grid_row = None
            self.grid_items_in_row = 0
            self.max_grid_items_per_row = 3
        
        # Check if we need a new row
        if self.grid_items_in_row == 0 or self.grid_items_in_row >= self.max_grid_items_per_row:
            self.current_grid_row = ctk.CTkFrame(self.grid_container, fg_color="transparent")
            self.current_grid_row.pack(fill="x", pady=5)
            self.grid_items_in_row = 0
        
        # Create the grid item
        grid_item = ctk.CTkFrame(self.current_grid_row, width=240, height=300, corner_radius=10)
        grid_item.pack(side="left", padx=5, pady=5)
        grid_item.pack_propagate(False)  # Prevent the frame from shrinking
        
        # Image container (fixed height)
        img_container = ctk.CTkFrame(grid_item, height=180, fg_color=self.colors["card_bg"])
        img_container.pack(fill="x")
        img_container.pack_propagate(False)
        
        # Get first image if available
        images = json.loads(result['images'])
        if images:
            try:
                thumbnail = self.create_thumbnail(images[0]['src'])
                if thumbnail:
                    img_label = ctk.CTkLabel(img_container, image=thumbnail, text="")
                    img_label.image = thumbnail
                    self.image_references.append(thumbnail)
                    img_label.pack(pady=10)
            except Exception:
                # Fallback icon if image fails
                ctk.CTkLabel(img_container, text="🌐", font=("Arial", 40)).pack(pady=40)
        else:
            # No image available
            ctk.CTkLabel(img_container, text="🌐", font=("Arial", 40)).pack(pady=40)
        
        # Content area
        content_area = ctk.CTkFrame(grid_item, fg_color="transparent")
        content_area.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Title
        title_label = ctk.CTkLabel(
            content_area, 
            text=result['title'][:40] + "..." if len(result['title']) > 40 else result['title'], 
            font=("Arial", 14, "bold"),
            wraplength=220)
        title_label.pack(anchor="w")
        
        # Domain
        domain_label = ctk.CTkLabel(
            content_area,
            text=urlparse(result['url']).netloc,
            font=("Arial", 12),
            text_color="gray"
        )
        domain_label.pack(anchor="w", pady=(0, 5))
        
        # Button container
        button_container = ctk.CTkFrame(grid_item, fg_color="transparent", height=40)
        button_container.pack(fill="x", side="bottom", padx=10, pady=10)
        
        # Action buttons
        open_btn = ctk.CTkButton(
            button_container,
            text="Open",
            command=lambda url=result['url']: webbrowser.open(url),
            width=70,
            height=28,
            font=("Arial", 12)
        )
        open_btn.pack(side="left", padx=(0, 5))
        
        # Save button
        save_btn = ctk.CTkButton(
            button_container,
            text="Save",
            command=lambda r=result: self.save_single_result(r),
            width=70,
            height=28,
            fg_color=self.colors["secondary"],
            font=("Arial", 12)
        )
        save_btn.pack(side="left")
        
        # Increment the counter for grid items in this row
        self.grid_items_in_row += 1
    
    def _display_result_card(self, result):
        """Display result as a detailed card"""
        result_frame = ctk.CTkFrame(self.results_canvas, corner_radius=10)
        result_frame.pack(fill="x", pady=10, padx=10)
        
        # Header with title and buttons
        header_frame = ctk.CTkFrame(result_frame, height=50)
        header_frame.pack(fill="x", pady=(0, 10))
        
        # Title
        ctk.CTkLabel(
            header_frame, 
            text=result['title'], 
            font=("Arial", 18, "bold")).pack(side="left", padx=15, pady=10)
        
        # Action buttons container
        actions_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        actions_frame.pack(side="right", padx=15, pady=10)
        
        # Buttons
        ctk.CTkButton(
            actions_frame, 
            text="🌐 Open URL", 
            width=100,
            command=lambda url=result['url']: webbrowser.open(url),
            fg_color=self.colors["primary"],
            font=("Arial", 12)
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            actions_frame, 
            text="💾 Save", 
            width=80,
            command=lambda r=result: self.save_single_result(r),
            fg_color=self.colors["secondary"],
            font=("Arial", 12)
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            actions_frame, 
            text="🔄 Similar", 
            width=80,
            command=lambda r=result: self.search_similar(r),
            fg_color=self.colors["accent"],
            font=("Arial", 12)
        ).pack(side="left", padx=5)
        
        # Content area with image gallery and text
        content_frame = ctk.CTkFrame(result_frame)
        content_frame.pack(fill="x", pady=10, padx=15)
        
        # Two columns: image gallery and text
        content_frame.grid_columnconfigure(0, weight=0)
        content_frame.grid_columnconfigure(1, weight=1)
        
        # Image gallery on the left (if available)
        gallery_frame = ctk.CTkFrame(content_frame, width=300, height=300)
        gallery_frame.grid(row=0, column=0, padx=(0, 15), sticky="ns")
        
        # Get images
        images = json.loads(result['images'])
        if images:
            # Show the first image as main image
            try:
                main_img = self.create_thumbnail(images[0]['src'])
                if main_img:
                    img_label = ctk.CTkLabel(gallery_frame, image=main_img, text="")
                    img_label.image = main_img
                    self.image_references.append(main_img)
                    img_label.pack(pady=(10, 5))
                    
                # Show thumbnails of additional images (up to 3)
                if len(images) > 1:
                    thumbnails_frame = ctk.CTkFrame(gallery_frame, fg_color="transparent")
                    thumbnails_frame.pack(fill="x", pady=5)
                    
                    for i in range(1, min(4, len(images))):
                        try:
                            thumb = self.create_thumbnail(images[i]['src'], size=(80, 80))
                            if thumb:
                                img_thumb = ctk.CTkLabel(thumbnails_frame, image=thumb, text="")
                                img_thumb.image = thumb
                                self.image_references.append(thumb)
                                img_thumb.pack(side="left", padx=5)
                        except Exception:
                            pass
                            
                    if len(images) > 4:
                        more_label = ctk.CTkLabel(
                            thumbnails_frame,
                            text=f"+{len(images) - 4} more",
                            font=("Arial", 12)
                        )
                        more_label.pack(side="left", padx=10)
            except Exception:
                ctk.CTkLabel(gallery_frame, text="No images available", font=("Arial", 14)).pack(pady=50)
        else:
            ctk.CTkLabel(gallery_frame, text="No images available", font=("Arial", 14)).pack(pady=50)
        
        # Text content on the right
        text_frame = ctk.CTkFrame(content_frame)
        text_frame.grid(row=0, column=1, sticky="nsew")
        
        # URL
        url_frame = ctk.CTkFrame(text_frame, fg_color="transparent")
        url_frame.pack(fill="x", pady=(10, 15))
        
        ctk.CTkLabel(
            url_frame,
            text="URL:",
            font=("Arial", 12, "bold"),
            width=50
        ).pack(side="left", padx=(10, 0))
        
        ctk.CTkLabel(
            url_frame,
            text=result['url'],
            font=("Arial", 12),
            anchor="w"
        ).pack(side="left", fill="x", expand=True, padx=5)
        
        # Content preview
        content_label = ctk.CTkLabel(
            text_frame,
            text="Content Preview:",
            font=("Arial", 12, "bold"),
            anchor="w"
        )
        content_label.pack(anchor="w", padx=10, pady=(0, 5))
        
        # Text preview in a scrollable frame
        preview_frame = ctk.CTkScrollableFrame(text_frame, height=180)
        preview_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        text_preview = result['body_content'][:800] + "..." if len(result['body_content']) > 800 else result['body_content']
        preview_text = ctk.CTkLabel(
            preview_frame, 
            text=text_preview, 
            wraplength=600,
            font=("Arial", 13),
            anchor="w",
            justify="left")
        preview_text.pack(anchor="w", fill="x")
        
        # Metadata section
        meta_frame = ctk.CTkFrame(result_frame, fg_color=self.colors["card_bg"])
        meta_frame.pack(fill="x", pady=(0, 10))
        
        meta_items = [
            {"label": "Domain", "value": urlparse(result['url']).netloc, "icon": "🌐"},
            {"label": "Updated", "value": result['timestamp'], "icon": "🕒"},
            {"label": "Images", "value": str(len(json.loads(result['images']))), "icon": "🖼️"},
            {"label": "Videos", "value": str(len(json.loads(result['videos']))), "icon": "🎥"},
            {"label": "Files", "value": str(len(json.loads(result['files']))), "icon": "📁"}
        ]
        
        for item in meta_items:
            item_frame = ctk.CTkFrame(meta_frame, fg_color="transparent")
            item_frame.pack(side="left", padx=15, pady=10, expand=True)
            
            ctk.CTkLabel(
                item_frame,
                text=f"{item['icon']} {item['label']}:",
                font=("Arial", 12),
            ).pack(anchor="w")
            
            ctk.CTkLabel(
                item_frame,
                text=item['value'],
                font=("Arial", 13, "bold"),
            ).pack(anchor="w")
            
    def save_single_result(self, result):
        """Save a single result to a file"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{urlparse(result['url']).netloc}_{timestamp}.json"
            filepath = os.path.join(self.settings["default_exports_folder"], filename)
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)
                
            self.add_notification(f"Result saved to {filename}", "success")
        except Exception as e:
            self.add_notification(f"Error saving result: {str(e)}", "error")
            
    def search_similar(self, result):
        """Search for content similar to this result"""
        # Extract keywords from title and content
        keywords = result['title'].split()[:3]  # First 3 words from title
        self.search_entry.delete(0, 'end')
        self.search_entry.insert(0, " ".join(keywords))
        self.domain_filter.delete(0, 'end')
        self.domain_filter.insert(0, urlparse(result['url']).netloc)
        self.start_scraping_thread()

    def start_scraping_thread(self):
        if not self.search_entry.get().strip():
            self.update_status("❌ Please enter a search query!")
            return
            
        self.scrape_btn.configure(state="disabled")
        self.progress.set(0)
        self.update_status("⏳ Scraping in progress...")
        
        # Get all filter values
        content_types = []
        if self.content_types["images"].get(): content_types.append("images")
        if self.content_types["videos"].get(): content_types.append("videos")
        if self.content_types["files"].get(): content_types.append("files")
        if self.content_types["links"].get(): content_types.append("links")
        if self.content_types["text"].get(): content_types.append("text")
        
        # Get advanced filters
        try:
            depth = int(self.depth_slider.get())
        except:
            depth = 2  # Default depth
            
        try:
            limit = int(self.limit_entry.get().strip())
        except:
            limit = 10  # Default limit
        
        filters = {
            "content_types": content_types,
            "domain": self.domain_filter.get().strip(),
            "limit": limit,
            "depth": depth,
            "date_range": self.date_options.get(),
            "language": self.language_option.get()
        }
        
        threading.Thread(
            target=self.run_scraper,
            args=(self.search_entry.get(), filters),
            daemon=True
        ).start()

    def run_scraper(self, query=None, filters=None, urls=None):
        try:
            try:
                from webscraper_o2 import scrape_urls, query_database
            except ImportError as e:
                self.log_message(f"Could not import webscraper_o2 module: {str(e)}", "ERROR")
                self.after(0, lambda: self.update_status("❌ Error: Web scraper module not found"))
                return
            
            # Set default filters if not provided
            if filters is None:
                filters = {}
            
            # Update status and UI
            if query:
                self.update_status(f"⏳ Scraping '{query}'...")
                self.log_message(f"Starting scraping for query: '{query}'", "INFO")
            elif urls:
                self.update_status(f"⏳ Scraping {len(urls)} URLs...")
                self.log_message(f"Starting scraping for specific URLs", "INFO")
            else:
                self.log_message("No query or URLs provided for scraping", "ERROR")
                self.after(0, lambda: self.update_status("❌ Error: No query or URLs provided"))
                return
                
            self.after(100, lambda: self.progress.set(0.2))
            
            # Ensure directory structure
            self.ensure_directories()
            
            # Run the scraper with filters
            self.log_message(f"Running scraper with filters: {filters}", "INFO")
            
            # Get filter values
            depth = filters.get("depth", 2)
            limit = filters.get("limit", 10)
            
            # Call scrape_urls with the appropriate parameters
            if urls:
                # If URLs are directly provided, use them
                self.log_message(f"Scraping specific URLs: {urls}", "INFO")
                scrape_result = scrape_urls(urls=urls, max_retries=3)
            else:
                # Otherwise use the query
                scrape_result = scrape_urls(query=query, max_retries=3)
            
            if scrape_result:
                self.after(100, lambda: self.progress.set(0.5))
                
                # Use the query for database search if available, otherwise use a generic term
                search_terms = query.split() if query else ["*"]
                
                self.log_message(f"Scraping complete. Querying database with terms: {search_terms}", "INFO")
                
                # Query the database with all filters
                results = query_database(
                    search_terms=search_terms,
                    content_type=filters["content_types"] or None,
                    limit=limit
                )

                self.after(100, lambda: self.progress.set(0.8))
                self.current_results = results
                
                # Update UI
                self.after(0, self.clear_results)
                
                if results:
                    self.log_message(f"Found {len(results)} results for {query or urls }", "INFO")
                    # Display each result
                    for result in results:
                        self.after(0, lambda r=result: self.display_result(r))
                else:
                    self.log_message("No results found", "WARNING")
                    self.after(0, self.show_empty_message)
                
                # Update status and history
                self.after(100, lambda: (
                    self.progress.set(1),
                    self.refresh_history(),
                    self.update_status(f"✅ Found {len(results)} results!")
                ))
                
        except Exception as e:
            self.log_message(f"Error in run_scraper: {str(e)}", "ERROR")
            # Use lambda with captured error message to avoid reference before assignment
            self.after(0, lambda err=str(e): self.update_status(f"❌ Error: {err}"))
        finally:
            self.after(0, lambda: self.scrape_btn.configure(state="normal"))

    def show_empty_message(self):
        empty_frame = ctk.CTkFrame(self.results_canvas)
        empty_frame.pack(pady=50)
        ctk.CTkLabel(empty_frame, 
                    text="🔍 No results found!\nTry adjusting your search filters.",
                    font=("Arial", 16)).pack()

    def export_results(self):
        if not self.current_results:
            messagebox.showwarning("No Data", "Nothing to export!")
            return
        
        file_path = ctk.filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("JSON Files", "*.json")]
        )
        
        if file_path:
            try:
                if file_path.endswith(".csv"):
                    self.export_to_csv(file_path)
                else:
                    self.export_to_json(file_path)
                self.update_status(f"✅ Exported {len(self.current_results)} items to {file_path}")
            except Exception as e:
                messagebox.showerror("Export Failed", str(e))

    def export_to_csv(self, path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Title", "URL", "Domain", "Images", "Videos", "Files"])
            for result in self.current_results:
                writer.writerow([
                    result["title"],
                    result["url"],
                    urlparse(result["url"]).netloc,
                    len(json.loads(result["images"])),
                    len(json.loads(result["videos"])),
                    len(json.loads(result["files"]))
                ])

    def export_to_json(self, path):
        export_data = [{
            "title": res["title"],
            "url": res["url"],
            "domain": urlparse(res["url"]).netloc,
            "content": res["body_content"][:1000],
            "metadata": {
                "images": len(json.loads(res["images"])),
                "videos": len(json.loads(res["videos"])),
                "files": len(json.loads(res["files"]))
            }
        } for res in self.current_results]
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2)

    def get_all_downloadable_files(self):
        """Get all downloadable files from the database"""
        try:
            # Connect to database
            conn = sqlite3.connect("database/scraped_data.db", timeout=10)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Query for files
            query = """
                SELECT p.url as page_url, p.title as page_title, 
                       json_extract(value, '$.url') as url, 
                       json_extract(value, '$.filename') as filename,
                       json_extract(value, '$.extension') as extension,
                       json_extract(value, '$.size') as size
                FROM pages p, 
                     json_each(p.files) as files
                WHERE json_valid(p.files) 
                  AND p.files != '[]'
                ORDER BY p.timestamp DESC
            """
            
            cursor.execute(query)
            files = [dict(row) for row in cursor.fetchall()]
            
            # Try to extract more file details
            for file in files:
                # Extract filename from URL if not available
                if not file.get('filename'):
                    file['filename'] = os.path.basename(file.get('url', ''))
                
                # Mark as downloaded if exists in our files directory
                file_path = os.path.join("database", "files", file.get('filename', ''))
                file['downloaded'] = os.path.exists(file_path)
                file['local_path'] = file_path if file['downloaded'] else None
            
            return files
            
        except Exception as e:
            self.log_message(f"Error getting downloadable files: {str(e)}", "ERROR")
            return []
        finally:
            if 'conn' in locals():
                conn.close()
    
    def show_downloadable_files(self):
        """Show downloadable files found during scraping"""
        # Create files directory if it doesn't exist
        files_dir = os.path.join("database", "files")
        os.makedirs(files_dir, exist_ok=True)
        
        popup = ctk.CTkToplevel(self)
        popup.title("Downloadable Files")
        popup.geometry("800x1600")
        popup.transient(self)
        popup.grab_set()
        
        files_frame = ctk.CTkFrame(popup)
        files_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header
        header_frame = ctk.CTkFrame(files_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 20))
        
        header_label = ctk.CTkLabel(
            header_frame,
            text="Downloadable Files",
            font=("Arial", 20, "bold")
        )
        header_label.pack(side="left", anchor="w")
        
        # Refresh button
        refresh_btn = ctk.CTkButton(
            header_frame,
            text="🔄 Refresh",
            command=lambda: self.refresh_files_list(files_list),
            width=100
        )
        refresh_btn.pack(side="right", padx=10)
        
        # Get files from database
        files = self.get_all_downloadable_files()
        
        # Stats label
        stats_label = ctk.CTkLabel(
            files_frame,
            text=f"Found {len(files)} files in database",
            font=("Arial", 14)
        )
        stats_label.pack(anchor="w", pady=(0, 10))
        
        # Create scrollable list
        files_list = ctk.CTkScrollableFrame(files_frame)
        files_list.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.populate_files_list(files_list, files)
    
    def populate_files_list(self, files_list, files):
        """Populate the files list with file data"""
        # Clear existing items
        for widget in files_list.winfo_children():
            widget.destroy()
            
        if not files:
            ctk.CTkLabel(
                files_list,
                text="No downloadable files found",
                font=("Arial", 14)
            ).pack(pady=20)
            return
        
        # Column headers
        header_frame = ctk.CTkFrame(files_list)
        header_frame.pack(fill="x", pady=5, padx=5)
        
        headers = ["#", "Filename", "Size", "Source", "Status", "Action"]
        widths = [40, 250, 80, 200, 100, 100]
        
        for i, (header, width) in enumerate(zip(headers, widths)):
            ctk.CTkLabel(
                header_frame,
                text=header,
                font=("Arial", 12, "bold"),
                width=width
            ).pack(side="left", padx=5)
            
        # List items
        for idx, file_data in enumerate(files):
            file_frame = ctk.CTkFrame(files_list)
            file_frame.pack(fill="x", pady=5, padx=5)
            
            # Get filename and size
            filename = file_data.get('filename') or os.path.basename(file_data.get('url', '')) or f"file_{idx}"
            size = file_data.get('size', 'Unknown')
            if isinstance(size, (int, float)):
                # Convert bytes to KB/MB
                if size < 1024:
                    size_text = f"{size} B"
                elif size < 1024 * 1024:
                    size_text = f"{size/1024:.1f} KB"
                else:
                    size_text = f"{size/(1024*1024):.1f} MB"
            else:
                size_text = str(size)
                
            # Source URL (shortened)
            source_url = file_data.get('page_url', '')
            if len(source_url) > 30:
                source_url = source_url[:27] + "..."
                
            # File status
            status = "Downloaded" if file_data.get('downloaded') else "Not Downloaded"
            status_color = self.colors["success"] if file_data.get('downloaded') else "#888888"
                
            # Add columns
            ctk.CTkLabel(
                file_frame,
                text=str(idx+1),
                width=40
            ).pack(side="left", padx=5)
            
            ctk.CTkLabel(
                file_frame,
                text=filename,
                width=250,
                anchor="w"
            ).pack(side="left", padx=5)
            
            ctk.CTkLabel(
                file_frame,
                text=size_text,
                width=80
            ).pack(side="left", padx=5)
            
            ctk.CTkLabel(
                file_frame,
                text=source_url,
                width=200
            ).pack(side="left", padx=5)
            
            status_label = ctk.CTkLabel(
                file_frame,
                text=status,
                width=100,
                text_color=status_color
            )
            status_label.pack(side="left", padx=5)
            
            # Action button
            if file_data.get('downloaded'):
                action_btn = ctk.CTkButton(
                    file_frame,
                    text="Open",
                    width=80,
                    command=lambda path=file_data.get('local_path'): self.open_file(path)
                )
            else:
                action_btn = ctk.CTkButton(
                    file_frame,
                    text="Download",
                    width=80,
                    command=lambda url=file_data.get('url'), idx=idx, status_label=status_label: 
                             self.download_file_and_update(url, idx, status_label, file_frame)
                )
            action_btn.pack(side="left", padx=5)
    
    def refresh_files_list(self, files_list):
        """Refresh the files list with new data"""
        files = self.get_all_downloadable_files()
        self.populate_files_list(files_list, files)
        self.add_notification(f"Found {len(files)} downloadable files", "info")
    
    def download_file_and_update(self, url, idx, status_label, file_frame):
        """Download a file and update the status"""
        if not url:
            self.add_notification("Invalid file URL", "error")
            return
            
        # Start download in a thread
        threading.Thread(
            target=self._download_file_thread,
            args=(url, idx, status_label, file_frame),
            daemon=True
        ).start()
    
    def _download_file_thread(self, url, idx, status_label, file_frame):
        """Thread for downloading files"""
        try:
            # Update UI
            self.after(0, lambda: status_label.configure(text="Downloading...", text_color=self.colors["warning"]))
            
            # Download the file
            file_path = self.download_file(url)
            
            if file_path:
                # Update UI to show success
                self.after(0, lambda: status_label.configure(text="Downloaded", text_color=self.colors["success"]))
                
                # Replace download button with open button
                for widget in file_frame.winfo_children():
                    if isinstance(widget, ctk.CTkButton):
                        self.after(0, widget.destroy)
                
                # Add new open button
                open_btn = ctk.CTkButton(
                    file_frame,
                    text="Open",
                    width=80,
                    command=lambda: self.open_file(file_path)
                )
                self.after(0, lambda: open_btn.pack(side="left", padx=5))
        except Exception as e:
            self.log_message(f"Error downloading file: {str(e)}", "ERROR")
            self.after(0, lambda: status_label.configure(text="Failed", text_color=self.colors["error"]))
    
    def download_file(self, url):
        """Download a file from URL and save to database/files folder"""
        try:
            self.update_status(f"⏳ Downloading file from {url}...")
            
            # Create files directory if not exists
            files_dir = os.path.join("database", "files")
            os.makedirs(files_dir, exist_ok=True)
            
            # Get filename from URL
            filename = os.path.basename(url)
            if not filename:
                # Generate a filename if none is found
                filename = f"file_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}{os.path.splitext(url)[1]}"
            
            # Sanitize filename
            filename = self.sanitize_filename(filename)
            
            # Download the file
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            file_path = os.path.join(files_dir, filename)
            
            # Save the file
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            self.add_notification(f"File downloaded: {filename}", "success")
            self.update_status(f"✅ File downloaded: {filename}")
            
            # Return file path
            return file_path
            
        except Exception as e:
            self.log_message(f"Error downloading file: {str(e)}", "ERROR")
            self.add_notification(f"Download failed: {str(e)}", "error")
            return None
    
    def open_file(self, file_path):
        """Open a file with the default application"""
        if not file_path or not os.path.exists(file_path):
            self.add_notification("File not found", "error")
            return
            
        try:
            if sys.platform == 'win32':
                os.startfile(file_path)
            elif sys.platform == 'darwin':  # macOS
                subprocess.Popen(['open', file_path])
            else:  # Linux
                subprocess.Popen(['xdg-open', file_path])
                
            self.log_message(f"Opened file: {file_path}", "INFO")
        except Exception as e:
            self.log_message(f"Error opening file: {str(e)}", "ERROR")
            self.add_notification(f"Error opening file: {str(e)}", "error")

    def update_status(self, message):
        self.status_label.configure(text=message)
        self.update_idletasks()

    def show_batch_processing(self):
        """Show batch processing popup"""
        popup = ctk.CTkToplevel(self)
        popup.title("Batch Processing")
        popup.geometry("700x600")  # Increased size
        popup.resizable(True, True)  # Make resizable
        
        # Batch processing frame
        batch_frame = ctk.CTkFrame(popup)
        batch_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header
        header_label = ctk.CTkLabel(
            batch_frame,
            text="Batch Scraping",
            font=("Arial", 20, "bold")
        )
        header_label.pack(anchor="w", pady=(0, 20))
        
        info_label = ctk.CTkLabel(
            batch_frame,
            text="Enter one search query per line for batch processing",
            font=("Arial", 14)
        )
        info_label.pack(anchor="w", pady=(0, 10))
        
        # Text entry for queries
        queries_textbox = ctk.CTkTextbox(
            batch_frame,
            height=300,  # Increased height
            font=("Arial", 14)
        )
        queries_textbox.pack(fill="both", expand=True, pady=10)
        
        # Options frame
        options_frame = ctk.CTkFrame(batch_frame)
        options_frame.pack(fill="x", pady=15)
        
        # Use current filters checkbox
        use_filters_var = ctk.BooleanVar(value=True)
        use_filters_check = ctk.CTkCheckBox(
            options_frame,
            text="Apply current filters to all queries",
            variable=use_filters_var,
            font=("Arial", 14)
        )
        use_filters_check.pack(side="left", padx=10)
        
        # Export results checkbox
        export_var = ctk.BooleanVar(value=True)
        export_check = ctk.CTkCheckBox(
            options_frame,
            text="Export results after completion",
            variable=export_var,
            font=("Arial", 14)
        )
        export_check.pack(side="right", padx=10)
        
        # Buttons frame
        buttons_frame = ctk.CTkFrame(batch_frame, fg_color="transparent")
        buttons_frame.pack(fill="x", pady=20)
        
        # Cancel button
        cancel_btn = ctk.CTkButton(
            buttons_frame,
            text="Cancel",
            fg_color=self.colors["error"],
            command=popup.destroy,
            width=120,
            font=("Arial", 14)
        )
        cancel_btn.pack(side="left", padx=10)
        
        # Start button
        start_btn = ctk.CTkButton(
            buttons_frame,
            text="Start Batch Processing",
            fg_color=self.colors["success"],
            command=lambda: self.start_batch_processing(
                queries_textbox.get("1.0", "end").splitlines(),
                use_filters_var.get(),
                export_var.get(),
                popup
            ),
            width=240,
            font=("Arial", 14)
        )
        start_btn.pack(side="right", padx=10)
        
    def start_batch_processing(self, queries, use_filters, export_results, popup):
        """Start batch processing of multiple queries"""
        # Filter out empty lines
        queries = [q.strip() for q in queries if q.strip()]
        
        if not queries:
            self.add_notification("No valid queries provided", "warning")
            return
            
        # Save current filters if needed
        current_filters = None
        if use_filters:
            content_types = []
            if self.content_types["images"].get(): content_types.append("images")
            if self.content_types["videos"].get(): content_types.append("videos")
            if self.content_types["files"].get(): content_types.append("files")
            if self.content_types["links"].get(): content_types.append("links")
            if self.content_types["text"].get(): content_types.append("text")
            
            current_filters = {
                "content_types": content_types,
                "domain": self.domain_filter.get().strip(),
                "limit": self.limit_entry.get().strip() or self.settings["max_results"],
                "language": self.language_option.get(),
                "depth": int(self.depth_slider.get())
            }
        
        # Close the popup
        popup.destroy()
        
        # Show batch progress popup
        self.show_batch_progress(queries, current_filters, export_results)
        
    def show_batch_progress(self, queries, filters, export_results):
        """Show batch progress popup and start processing"""
        popup = ctk.CTkToplevel(self)
        popup.title("Batch Progress")
        popup.geometry("700x500")  # Increased size
        popup.resizable(True, True)  # Make resizable
        popup.transient(self)  # Make it stay on top of main window
        
        # Progress frame
        progress_frame = ctk.CTkFrame(popup)
        progress_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header
        header_label = ctk.CTkLabel(
            progress_frame,
            text="Batch Processing Progress",
            font=("Arial", 20, "bold")
        )
        header_label.pack(anchor="w", pady=(0, 20))
        
        # Info label
        info_label = ctk.CTkLabel(
            progress_frame,
            text=f"Processing {len(queries)} queries",
            font=("Arial", 14)
        )
        info_label.pack(anchor="w", pady=(0, 10))
        
        # Current query label
        current_query_label = ctk.CTkLabel(
            progress_frame,
            text="Current query: -",
            font=("Arial", 14)
        )
        current_query_label.pack(anchor="w", pady=5)
        
        # Progress bars
        query_progress_label = ctk.CTkLabel(
            progress_frame,
            text="Query progress:",
            font=("Arial", 14)
        )
        query_progress_label.pack(anchor="w", pady=(15, 5))
        
        query_progress = ctk.CTkProgressBar(progress_frame)
        query_progress.pack(fill="x", pady=(0, 15))
        query_progress.set(0)
        
        total_progress_label = ctk.CTkLabel(
            progress_frame,
            text="Total progress:",
            font=("Arial", 14)
        )
        total_progress_label.pack(anchor="w", pady=(5, 5))
        
        total_progress = ctk.CTkProgressBar(progress_frame)
        total_progress.pack(fill="x")
        total_progress.set(0)
        
        # Status label
        status_label = ctk.CTkLabel(
            progress_frame,
            text="Preparing...",
            font=("Arial", 14)
        )
        status_label.pack(anchor="w", pady=15)
        
        # Results label
        results_label = ctk.CTkLabel(
            progress_frame,
            text="Results: 0",
            font=("Arial", 14)
        )
        results_label.pack(anchor="w")
        
        # Cancel button
        cancel_btn = ctk.CTkButton(
            progress_frame,
            text="Cancel Batch Process",
            fg_color=self.colors["error"],
            command=lambda: self.cancel_batch_processing(popup),
            font=("Arial", 14)
        )
        cancel_btn.pack(pady=20)
        
        # Start the batch processing
        self.cancel_flag = False
        self.batch_results = []
        
        # Start the batch processing thread
        threading.Thread(
            target=self.process_batch_queries,
            args=(queries, filters, export_results, popup, current_query_label, 
                  query_progress, total_progress, status_label, results_label),
            daemon=True
        ).start()
    
    def process_batch_queries(self, queries, filters, export_results, popup, 
                             current_query_label, query_progress, total_progress, 
                             status_label, results_label):
        """Process batch queries in a thread"""
        try:
            from webscraper_o2 import scrape_urls, query_database
        except ImportError as e:
            self.log_message(f"Could not import webscraper_o2 module: {str(e)}", "ERROR")
            self.after(0, lambda: status_label.configure(text="❌ Error: Web scraper module not found"))
            return
        
        total_results = []
        self.log_message(f"Starting batch processing of {len(queries)} queries", "INFO")
        
        for i, query in enumerate(queries):
            if self.cancel_flag:
                self.log_message("Batch processing cancelled by user", "WARNING")
                self.after(0, lambda: status_label.configure(text="Cancelled"))
                break
                
            # Update UI
            self.after(0, lambda q=query: current_query_label.configure(text=f"Current query: {q}"))
            self.after(0, lambda p=i/len(queries): total_progress.set(p))
            self.after(0, lambda: status_label.configure(text=f"Scraping for query {i+1} of {len(queries)}"))
            
            try:
                # Reset query progress
                self.after(0, lambda: query_progress.set(0))
                
                # Ensure directories
                self.ensure_directories()
                
                self.log_message(f"Processing batch query {i+1}/{len(queries)}: '{query}'", "INFO")
                
                # Scrape URLs
                if scrape_urls(query=query):
                    self.after(0, lambda: query_progress.set(0.5))
                    
                    # Query database
                    search_terms = query.split()
                    self.log_message(f"Querying database for batch query: '{query}'", "INFO")
                    
                    results = query_database(
                        search_terms=search_terms,
                        content_type=filters["content_types"] if filters else None,
                        limit=int(filters["limit"]) if filters and filters["limit"] else 10
                    )
                    
                    # Update results
                    if results:
                        total_results.extend(results)
                        self.log_message(f"Found {len(results)} results for batch query: '{query}'", "INFO")
                        self.after(0, lambda r=len(total_results): results_label.configure(text=f"Results: {r}"))
                    else:
                        self.log_message(f"No results found for batch query: '{query}'", "WARNING")
                    
                    # Complete this query
                    self.after(0, lambda: query_progress.set(1))
                    
                    # Save results for this query if needed
                    if export_results and results:
                        self.after(0, lambda: status_label.configure(text=f"Saving results for query {i+1}"))
                        self.save_batch_results(results, query)
                        
            except Exception as e:
                self.log_message(f"Error processing batch query '{query}': {str(e)}", "ERROR")
                self.after(0, lambda err=str(e): status_label.configure(text=f"Error: {err}"))
                
        # Complete
        self.log_message(f"Batch processing complete. Found {len(total_results)} total results", "INFO")
        self.after(0, lambda: total_progress.set(1))
        self.after(0, lambda: status_label.configure(
            text=f"Completed: {len(total_results)} results from {len(queries)} queries"))
        
        # Store results
        self.batch_results = total_results
        
        # Add completion buttons
        self.after(0, lambda: self.add_batch_complete_buttons(popup, total_results))
    
    def add_batch_complete_buttons(self, popup, results):
        """Add buttons to complete batch processing"""
        buttons_frame = ctk.CTkFrame(popup, fg_color="transparent")
        buttons_frame.pack(side="bottom", fill="x", padx=20, pady=20)
        
        # Close button
        close_btn = ctk.CTkButton(
            buttons_frame,
            text="Close",
            command=popup.destroy,
            fg_color=self.colors["error"],
            width=120,
            font=("Arial", 14)
        )
        close_btn.pack(side="left", padx=10)
        
        # View results button
        if results:
            view_btn = ctk.CTkButton(
                buttons_frame,
                text="View Results",
                command=lambda: self.show_batch_results(results, popup),
                fg_color=self.colors["success"],
                width=200,
                font=("Arial", 14)
            )
            view_btn.pack(side="right", padx=10)
    
    def cancel_batch_processing(self, popup):
        """Cancel the batch processing"""
        self.cancel_flag = True
        popup.destroy()
        self.add_notification("Batch processing cancelled", "warning")
        
    def save_batch_results(self, results, query):
        """Save batch results to a file"""
        if not results:
            return
            
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"batch_{query.replace(' ', '_')}_{timestamp}.json"
        filepath = os.path.join(self.settings["default_exports_folder"], filename)
        
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2)
        except Exception as e:
            self.add_notification(f"Error saving batch results: {str(e)}", "error")
            
    def show_batch_results(self, results, popup):
        """Show batch results in the main window"""
        popup.destroy()
        
        # Clear current results
        self.clear_results()
        
        # Display batch results
        self.current_results = results
        for result in results:
            self.display_result(result)
            
        # Update stats
        self.stats_label.configure(text=f"Found: {len(results)} results")
        self.tabs.set("📄 Current Results")
        
        # Notification
        self.add_notification(f"Loaded {len(results)} batch results", "success")
        
    def update_dashboard(self):
        """Update dashboard with analytics data"""
        try:
            # Get statistics
            stats = self.get_scraping_statistics()
            
            # Update stat cards
            if hasattr(self, 'stat_cards') and len(self.stat_cards) >= 4:
                stat_cards = self.stat_cards
                
                # Total scrapes
                stat_cards[0].winfo_children()[1].winfo_children()[1].configure(
                    text=str(stats["total_scrapes"]))
                
                # Pages indexed
                stat_cards[1].winfo_children()[1].winfo_children()[1].configure(
                    text=str(stats["pages_indexed"]))
                
                # Media files
                stat_cards[2].winfo_children()[1].winfo_children()[1].configure(
                    text=str(stats["media_files"]))
                
                # Average search time
                stat_cards[3].winfo_children()[1].winfo_children()[1].configure(
                    text=f"{stats['avg_search_time']:.1f}s")
            
            # Update charts
            if hasattr(self, 'chart_frames'):
                self.create_dashboard_charts(stats)
                
        except Exception as e:
            print(f"Error updating dashboard: {e}")
            
    def get_scraping_statistics(self):
        """Get scraping statistics from database"""
        stats = {
            "total_scrapes": 0,
            "pages_indexed": 0,
            "media_files": 0,
            "avg_search_time": 0,
            "content_types": {"images": 0, "videos": 0, "files": 0, "links": 0, "text": 0},
            "domains": {},
            "scrape_history": {},
            "file_types": {}
        }
        
        # Count files in history
        try:
            history_files = os.listdir("database/scraped_results")
            stats["total_scrapes"] = len([f for f in history_files if f.endswith(".txt")])
            
            # Read database to get more stats (mock data for now)
            # In a real implementation, this would connect to SQLite or another database
            stats["pages_indexed"] = stats["total_scrapes"] * 5  # Estimate
            stats["media_files"] = stats["total_scrapes"] * 15  # Estimate
            stats["avg_search_time"] = 2.3  # Mock average search time
            
            # Mock content type distribution
            stats["content_types"] = {
                "images": 65,
                "videos": 15,
                "files": 10,
                "links": 120,
                "text": 200
            }
            
            # Mock top domains
            stats["domains"] = {
                "example.com": 25,
                "wikipedia.org": 18,
                "github.com": 15,
                "medium.com": 12,
                "stackoverflow.com": 10,
                "other": 20
            }
            
            # Mock scraping history (last 7 days)
            today = datetime.datetime.now().date()
            stats["scrape_history"] = {
                (today - datetime.timedelta(days=i)).strftime("%Y-%m-%d"): 
                stats["total_scrapes"] // 7 + (5 - i if i < 5 else 0)
                for i in range(7)
            }
            
            # Mock file types
            stats["file_types"] = {
                "jpg": 45,
                "png": 25,
                "pdf": 15,
                "zip": 8,
                "doc": 5,
                "other": 12
            }
            
        except Exception as e:
            print(f"Error getting statistics: {e}")
            
        return stats
        
    def create_dashboard_charts(self, stats):
        """Create charts for dashboard"""
        for chart_frame in self.chart_frames:
            # Clear previous chart if any
            for widget in chart_frame["area"].winfo_children():
                widget.destroy()
                
            # Create appropriate chart based on title
            title = chart_frame["title"]
            
            if title == "Content Types Distribution":
                self.create_pie_chart(
                    chart_frame["area"],
                    stats["content_types"],
                    "Content Types"
                )
            elif title == "Top Domains":
                self.create_bar_chart(
                    chart_frame["area"],
                    stats["domains"],
                    "Top Domains"
                )
            elif title == "Scraping History":
                self.create_line_chart(
                    chart_frame["area"],
                    stats["scrape_history"],
                    "Daily Scrapes"
                )
            elif title == "File Types Distribution":
                self.create_pie_chart(
                    chart_frame["area"],
                    stats["file_types"],
                    "File Types"
                )
                
    def create_pie_chart(self, parent, data, title):
        """Create a pie chart in the given parent frame"""
        fig, ax = plt.subplots(figsize=(4, 3), dpi=100)
        
        # Plot data
        wedges, texts, autotexts = ax.pie(
            data.values(),
            labels=None,
            autopct='%1.1f%%',
            startangle=90,
            wedgeprops={'width': 0.5}
        )
        
        # Equal aspect ratio ensures that pie is drawn as a circle
        ax.axis('equal')
        ax.set_title(title)
        
        # Add legend
        ax.legend(
            wedges,
            data.keys(),
            loc="center left",
            bbox_to_anchor=(1, 0, 0.5, 1)
        )
        
        # Style for dark theme
        fig.patch.set_facecolor('#2b2b2b')
        ax.set_facecolor('#2b2b2b')
        
        for text in texts + autotexts + [ax.title] + ax.get_legend().get_texts():
            text.set_color('white')
            
        # Embed in tkinter
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        
    def create_bar_chart(self, parent, data, title):
        """Create a bar chart in the given parent frame"""
        fig, ax = plt.subplots(figsize=(4, 3), dpi=100)
        
        # Plot data
        keys = list(data.keys())
        vals = list(data.values())
        
        bars = ax.bar(
            range(len(keys)),
            vals,
            color='#1f6aa5'
        )
        
        # Customize
        ax.set_title(title)
        ax.set_ylabel('Count')
        
        # Properly set ticks first, then labels
        ax.set_xticks(range(len(keys)))
        ax.set_xticklabels(keys, rotation=45, ha='right')
        
        # Style for dark theme
        fig.patch.set_facecolor('#2b2b2b')
        ax.set_facecolor('#2b2b2b')
        ax.spines['bottom'].set_color('white')
        ax.spines['top'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.spines['right'].set_color('white')
        ax.tick_params(axis='x', colors='white')
        ax.tick_params(axis='y', colors='white')
        ax.set_title(title, color='white')
        ax.yaxis.label.set_color('white')
        
        # Tight layout
        fig.tight_layout()
        
        # Embed in tkinter
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        
    def create_line_chart(self, parent, data, title):
        """Create a line chart in the given parent frame"""
        fig, ax = plt.subplots(figsize=(4, 3), dpi=100)
        
        # Sort data by date
        sorted_data = sorted(data.items())
        dates = [item[0] for item in sorted_data]
        values = [item[1] for item in sorted_data]
        
        # Plot data
        ax.plot(
            range(len(dates)),
            values,
            marker='o',
            linestyle='-',
            color='#4CAF50'
        )
        
        # Customize
        ax.set_title(title)
        ax.set_ylabel('Scrapes')
        
        # Properly set ticks first, then labels
        ax.set_xticks(range(len(dates)))
        ax.set_xticklabels(dates, rotation=45, ha='right')
        
        # Style for dark theme
        fig.patch.set_facecolor('#2b2b2b')
        ax.set_facecolor('#2b2b2b')
        ax.spines['bottom'].set_color('white')
        ax.spines['top'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.spines['right'].set_color('white')
        ax.tick_params(axis='x', colors='white')
        ax.tick_params(axis='y', colors='white')
        ax.set_title(title, color='white')
        ax.yaxis.label.set_color('white')
        
        # Tight layout
        fig.tight_layout()
        
        # Embed in tkinter
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        
    def clear_database_cache(self):
        """Clear database cache files"""
        try:
            cache_path = "database/cache"
            if os.path.exists(cache_path):
                shutil.rmtree(cache_path)
                os.makedirs(cache_path)
                self.add_notification("Database cache cleared", "success")
            else:
                os.makedirs(cache_path)
                self.add_notification("Cache directory created", "info")
        except Exception as e:
            self.add_notification(f"Error clearing cache: {str(e)}", "error")
            
    def manage_cache(self):
        """Manage application cache"""
        cache_dir = os.path.join("database", "cache")
        os.makedirs(cache_dir, exist_ok=True)
        
        # Calculate cache size
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(cache_dir):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.exists(fp):
                    total_size += os.path.getsize(fp)
                
        # Convert to MB
        total_size_mb = total_size / (1024 * 1024)
        
        # Show cache management popup
        popup = ctk.CTkToplevel(self)
        popup.title("Cache Management")
        popup.geometry("500x500")
        popup.transient(self)
        popup.grab_set()
        
        frame = ctk.CTkFrame(popup)
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(
            frame,
            text="Cache Management",
            font=("Arial", 20, "bold")
        ).pack(anchor="w", pady=(0, 20))
        
        # Current cache size
        size_frame = ctk.CTkFrame(frame, fg_color="transparent")
        size_frame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(
            size_frame,
            text="Current Cache Size:",
            font=("Arial", 14, "bold")
        ).pack(side="left")
        
        size_value = ctk.CTkLabel(
            size_frame,
            text=f"{total_size_mb:.2f} MB",
            font=("Arial", 14),
            text_color=self.colors["primary"]
        )
        size_value.pack(side="left", padx=10)
        
        # Cache details - display type and size
        details_frame = ctk.CTkFrame(frame)
        details_frame.pack(fill="x", pady=20)
        
        ctk.CTkLabel(
            details_frame, 
            text="Cache Details",
            font=("Arial", 16, "bold")
        ).pack(anchor="w", padx=10, pady=10)
        
        # Calculate sizes of different cache types
        cache_types = {
            "Thumbnails": os.path.join(cache_dir, "thumbnails"),
            "Search Results": os.path.join(cache_dir, "search"),
            "Downloaded Files": os.path.join("database", "files"), 
            "Logs": os.path.join("database", "logs")
        }
        
        # Create a scrollable frame for the cache types
        types_list = ctk.CTkScrollableFrame(details_frame, height=150)
        types_list.pack(fill="x", padx=10, pady=10)
        
        for cache_type, path in cache_types.items():
            type_frame = ctk.CTkFrame(types_list)
            type_frame.pack(fill="x", pady=5)
            
            # Calculate size
            type_size = 0
            if os.path.exists(path):
                if os.path.isdir(path):
                    for dirpath, dirnames, filenames in os.walk(path):
                        for f in filenames:
                            fp = os.path.join(dirpath, f)
                            if os.path.exists(fp):
                                type_size += os.path.getsize(fp)
                else:
                    type_size = os.path.getsize(path)
                    
            # Convert to readable format
            if type_size < 1024:
                size_str = f"{type_size} B"
            elif type_size < 1024 * 1024:
                size_str = f"{type_size/1024:.1f} KB"
            else:
                size_str = f"{type_size/(1024*1024):.1f} MB"
                
            # Display type and size
            ctk.CTkLabel(
                type_frame,
                text=cache_type,
                font=("Arial", 14)
            ).pack(side="left", padx=10)
            
            ctk.CTkLabel(
                type_frame,
                text=size_str,
                font=("Arial", 14)
            ).pack(side="right", padx=10)
        
        # Cache options
        options_frame = ctk.CTkFrame(frame)
        options_frame.pack(fill="x", pady=20)
        
        ctk.CTkLabel(
            options_frame,
            text="Cache Actions",
            font=("Arial", 16, "bold")
        ).pack(anchor="w", padx=10, pady=10)
        
        buttons_frame = ctk.CTkFrame(options_frame, fg_color="transparent")
        buttons_frame.pack(fill="x", padx=10, pady=10)
        
        # Clear thumbnails button
        ctk.CTkButton(
            buttons_frame,
            text="Clear Image Thumbnails",
            command=lambda: self.clear_cache_type("thumbnails", size_value)
        ).pack(fill="x", pady=5)
        
        # Clear search results cache
        ctk.CTkButton(
            buttons_frame,
            text="Clear Search Results Cache",
            command=lambda: self.clear_cache_type("search", size_value)
        ).pack(fill="x", pady=5)
        
        # Optimize database
        ctk.CTkButton(
            buttons_frame,
            text="Optimize Database",
            command=self.optimize_database,
            fg_color=self.colors["secondary"]
        ).pack(fill="x", pady=5)
        
        # Clear all cache
        ctk.CTkButton(
            buttons_frame,
            text="Clear All Cache",
            command=lambda: self.clear_all_cache(size_value),
            fg_color=self.colors["error"]
        ).pack(fill="x", pady=10)
        
        # Set cache settings
        settings_frame = ctk.CTkFrame(frame)
        settings_frame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(
            settings_frame,
            text="Cache Settings",
            font=("Arial", 16, "bold")
        ).pack(anchor="w", padx=10, pady=10)
        
        # Cache limit setting
        limit_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        limit_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            limit_frame,
            text="Cache Size Limit (MB):",
            font=("Arial", 14)
        ).pack(side="left")
        
        cache_limit = ctk.CTkEntry(
            limit_frame,
            width=100
        )
        cache_limit.insert(0, str(self.settings.get("cache_limit_mb", 100)))
        cache_limit.pack(side="left", padx=10)
        
        # Auto-clear cache checkbox
        auto_clear_var = ctk.BooleanVar(value=self.settings.get("auto_clear_cache", True))
        
        auto_clear = ctk.CTkCheckBox(
            settings_frame,
            text="Auto-clear cache when limit is reached",
            variable=auto_clear_var,
            font=("Arial", 14)
        )
        auto_clear.pack(anchor="w", padx=10, pady=10)
        
        # Save settings button
        ctk.CTkButton(
            settings_frame,
            text="Save Cache Settings",
            command=lambda: self.save_cache_settings(cache_limit.get(), auto_clear_var.get()),
            fg_color=self.colors["primary"]
        ).pack(fill="x", padx=10, pady=10)
    
    def clear_cache_type(self, cache_type, size_label=None):
        """Clear a specific type of cache"""
        try:
            cache_dir = os.path.join("database", "cache")
            type_path = os.path.join(cache_dir, cache_type)
            
            if os.path.exists(type_path):
                if os.path.isdir(type_path):
                    shutil.rmtree(type_path)
                    os.makedirs(type_path)
                else:
                    os.remove(type_path)
                    
                self.add_notification(f"{cache_type.title()} cache cleared", "success")
                
                # Update size label if provided
                if size_label:
                    # Recalculate total cache size
                    total_size = 0
                    for dirpath, dirnames, filenames in os.walk(cache_dir):
                        for f in filenames:
                            fp = os.path.join(dirpath, f)
                            if os.path.exists(fp):
                                total_size += os.path.getsize(fp)
                    
                    # Convert to MB
                    total_size_mb = total_size / (1024 * 1024)
                    
                    # Update label
                    size_label.configure(text=f"{total_size_mb:.2f} MB")
            else:
                os.makedirs(type_path, exist_ok=True)
                self.add_notification(f"{cache_type.title()} cache directory created", "info")
                
        except Exception as e:
            self.log_message(f"Error clearing {cache_type} cache: {str(e)}", "ERROR")
            self.add_notification(f"Error clearing cache: {str(e)}", "error")
    
    def clear_all_cache(self, size_label=None):
        """Clear all cache types"""
        try:
            # Clear main cache directory
            cache_dir = os.path.join("database", "cache")
            if os.path.exists(cache_dir):
                shutil.rmtree(cache_dir)
                os.makedirs(cache_dir)
                
            # Create subdirectories
            os.makedirs(os.path.join(cache_dir, "thumbnails"), exist_ok=True)
            os.makedirs(os.path.join(cache_dir, "search"), exist_ok=True)
            
            self.add_notification("All cache cleared successfully", "success")
            
            # Update size label if provided
            if size_label:
                size_label.configure(text="0.00 MB")
                
        except Exception as e:
            self.log_message(f"Error clearing all cache: {str(e)}", "ERROR")
            self.add_notification(f"Error clearing cache: {str(e)}", "error")
    
    def save_cache_settings(self, limit, auto_clear):
        """Save cache settings to application settings"""
        try:
            # Validate limit
            try:
                limit = float(limit)
                if limit <= 0:
                    limit = 100  # Default
            except:
                limit = 100  # Default
                
            # Update settings
            self.settings["cache_limit_mb"] = limit
            self.settings["auto_clear_cache"] = bool(auto_clear)
            
            # Save settings
            self.save_settings()
            
            self.add_notification("Cache settings saved", "success")
            
        except Exception as e:
            self.log_message(f"Error saving cache settings: {str(e)}", "ERROR")
            self.add_notification(f"Error saving settings: {str(e)}", "error")
    
    def optimize_database(self):
        """Optimize database for better performance"""
        try:
            conn = sqlite3.connect("database/scraped_data.db")
            cursor = conn.cursor()
            
            # Create indexes if they don't exist
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pages_title ON pages(title)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pages_timestamp ON pages(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pages_body ON pages(body_content)")
            
            # Run ANALYZE to update statistics
            cursor.execute("ANALYZE")
            
            # Vacuum to clean up space
            cursor.execute("VACUUM")
            
            conn.commit()
            conn.close()
            
            self.add_notification("Database optimized successfully", "success")
            
        except Exception as e:
            self.log_message(f"Error optimizing database: {str(e)}", "ERROR")
            self.add_notification(f"Error optimizing database: {str(e)}", "error")
            
    def export_database(self):
        """Export database to a file"""
        file_path = ctk.filedialog.asksaveasfilename(
            defaultextension=".db",
            filetypes=[("SQLite Database", "*.db"), ("All Files", "*.*")]
        )
        
        if file_path:
            try:
                # Copy the database file
                shutil.copy("database/scraper.db", file_path)
                self.add_notification(f"Database exported to {file_path}", "success")
            except Exception as e:
                self.add_notification(f"Error exporting database: {str(e)}", "error")
                
    def import_database(self):
        """Import database from a file"""
        file_path = ctk.filedialog.askopenfilename(
            filetypes=[("SQLite Database", "*.db"), ("All Files", "*.*")]
        )
        
        if file_path:
            try:
                # Back up current database
                backup_path = "database/scraper_backup.db"
                if os.path.exists("database/scraper.db"):
                    shutil.copy("database/scraper.db", backup_path)
                
                # Import the new database
                shutil.copy(file_path, "database/scraper.db")
                self.add_notification(f"Database imported successfully", "success")
                
                # Refresh data
                self.refresh_history()
                self.update_dashboard()
            except Exception as e:
                self.add_notification(f"Error importing database: {str(e)}", "error")
                
    def apply_settings(self):
        """Apply and save settings"""
        try:
            # Update settings from controls
            for key, control in self.settings_controls.items():
                if isinstance(control, ctk.CTkSwitch):
                    self.settings[key] = control.get()
                elif isinstance(control, ctk.CTkEntry):
                    self.settings[key] = control.get()
                elif isinstance(control, ctk.CTkSlider):
                    self.settings[key] = int(control.get())
            
            # Save settings to file
            self.save_settings()
            
            # Notification
            self.add_notification("Settings saved successfully", "success")
            
        except Exception as e:
            self.add_notification(f"Error saving settings: {str(e)}", "error")

    def clear_history(self):
        """Clear all history files after confirmation"""
        confirm = messagebox.askyesno(
            "Clear History",
            "Are you sure you want to delete all search history?\nThis action cannot be undone.",
            parent=self
        )
        
        if confirm:
            try:
                folder_path = os.path.join("database", "scraped_results")
                files_deleted = 0
                
                for filename in os.listdir(folder_path):
                    file_path = os.path.join(folder_path, filename)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        files_deleted += 1
                
                self.refresh_history()
                self.add_notification(f"History cleared. {files_deleted} files deleted.", "success")
            except Exception as e:
                self.add_notification(f"Error clearing history: {str(e)}", "error")

    def clear_results(self):
        """Clear all results from the display"""
        for widget in self.results_canvas.winfo_children():
            widget.destroy()
            
        # Reset grid display variables
        if hasattr(self, 'grid_container'):
            delattr(self, 'grid_container')
            self.grid_items_in_row = 0
            
    def refresh_history(self):
        """Refresh the history view with recent searches"""
        try:
            # Clear current history
            for widget in self.history_list.winfo_children():
                widget.destroy()
                
            # Get history files
            history_path = os.path.join("database", "scraped_results")
            if os.path.exists(history_path):
                history_files = [f for f in os.listdir(history_path) if f.endswith(".txt")]
                history_files.sort(key=lambda x: os.path.getmtime(os.path.join(history_path, x)), reverse=True)
                
                self.history_files = set(history_files)
                
                # Display history items
                for file in history_files[:50]:  # Show only the latest 50 entries
                    self.create_history_item(file, os.path.join(history_path, file))
                    
                # Update history count
                if hasattr(self, 'history_title'):
                    self.history_title.configure(text=f"Search History ({len(history_files)})")
        except Exception as e:
            print(f"Error refreshing history: {e}")
            
    def create_history_item(self, filename, filepath):
        """Create a history item entry"""
        try:
            # Create history item frame
            item_frame = ctk.CTkFrame(self.history_list, corner_radius=8)
            item_frame.pack(fill="x", padx=10, pady=5)
            
            # Try to extract the search query from the filename
            search_query = filename.replace(".txt", "").replace("_", " ")
            timestamp = datetime.datetime.fromtimestamp(os.path.getmtime(filepath))
            date_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            
            # Query and timestamp
            ctk.CTkLabel(
                item_frame,
                text=search_query,
                font=("Arial", 14, "bold")
            ).pack(anchor="w", padx=15, pady=(10, 5))
            
            ctk.CTkLabel(
                item_frame,
                text=f"🕒 {date_str}",
                font=("Arial", 12),
                text_color="gray"
            ).pack(anchor="w", padx=15, pady=(0, 5))
            
            # Action buttons
            btn_frame = ctk.CTkFrame(item_frame, fg_color="transparent")
            btn_frame.pack(fill="x", padx=15, pady=(5, 10))
            
            # Load button
            ctk.CTkButton(
                btn_frame,
                text="Load Results",
                command=lambda f=filepath: self.load_history_results(f),
                font=("Arial", 12),
                width=120,
                height=30
            ).pack(side="left", padx=(0, 10))
            
            # Delete button
            ctk.CTkButton(
                btn_frame,
                text="Delete",
                command=lambda f=filepath: self.delete_history_item(f),
                font=("Arial", 12),
                fg_color=self.colors["error"],
                width=80,
                height=30
            ).pack(side="left")
        except Exception as e:
            print(f"Error creating history item: {e}")
            
    def load_history_results(self, file_path):
        """Load results from a history file and display them"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                results_data = f.read()
            
            # Clear previous results
            self.clear_results()
            
            # Parse the results
            results = []
            current_result = {}
            lines = results_data.split('\n')
            i = 0
            
            while i < len(lines):
                line = lines[i].strip()
                
                if line.startswith("Title:"):
                    # Start of a new result
                    if current_result and any(current_result.values()):
                        results.append(current_result)
                    current_result = {"title": line[6:].strip()}
                elif line.startswith("URL:") and current_result:
                    current_result["url"] = line[4:].strip()
                elif line.startswith("Body:") and current_result:
                    # Body content spans multiple lines
                    body_content = []
                    i += 1
                    while i < len(lines) and not (lines[i].strip().startswith("Title:") or 
                                                 lines[i].strip() == "--------------------"):
                        body_content.append(lines[i])
                        i += 1
                    current_result["body"] = "\n".join(body_content)
                    continue  # Skip the i+=1 at the end of the loop
                elif line == "--------------------":
                    # End of current result
                    if current_result and any(current_result.values()):
                        results.append(current_result)
                    current_result = {}
                
                i += 1
            
            # Add the last result if exists
            if current_result and any(current_result.values()):
                results.append(current_result)
            
            # Display results in the UI
            if results:
                for result in results:
                    if not all(key in result for key in ["title", "url", "body"]):
                        continue
                        
                    self.add_search_result(
                        title=result.get("title", "No Title"),
                        url=result.get("url", ""),
                        body=result.get("body", "No content"),
                        update_count=False
                    )
                
                # Update the results count
                self.update_results_count(len(results))
                
                # Extract query from filename
                filename = os.path.basename(file_path)
                query = filename.split('__')[0].replace('_', ' ')
                
                # Update search entry with the original query
                self.search_entry.delete(0, ctk.END)
                self.search_entry.insert(0, query)
                
                # Show success notification
                self.add_notification(f"Loaded {len(results)} results from history", "success")
            else:
                self.add_notification("No valid results found in the history file", "warning")
        
        except Exception as e:
            print(f"Error loading history results: {str(e)}")
            self.add_notification(f"Error loading history: {str(e)}", "error")
            
    def open_latest_scrape_file(self):
        """Opens the latest .txt file in database/scraped_results"""
        try:
            folder = os.path.join("database", "scraped_results")
            if not os.path.exists(folder):
                self.add_notification("No 'scraped_results' folder found.", "error")
                return

            files = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".txt")]
            if not files:
                self.add_notification("No result files found.", "warning")
                return

            latest_file = max(files, key=os.path.getmtime)

            # Cross-platform file opener
            if platform.system() == "Windows":
                os.startfile(latest_file)
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", latest_file])
            else:  # Linux, etc.
                subprocess.run(["xdg-open", latest_file])

            self.log_message(f"Opened latest scrape result: {latest_file}", "INFO")

        except Exception as e:
            self.log_message(f"Error opening scrape result: {str(e)}", "ERROR")
            self.add_notification(f"❌ Failed to open file: {str(e)}", "error")


    def delete_history_item(self, filepath):
        """Delete a history item"""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                self.refresh_history()
                self.add_notification("History item deleted", "success")
        except Exception as e:
            self.add_notification(f"Error deleting file: {str(e)}", "error")

    def toggle_sidebar(self):
        """Toggle the sidebar between collapsed and expanded states"""
        if self.sidebar_expanded:
            # Collapse sidebar
            self.sidebar_frame.configure(width=50)
            self.sidebar.grid_forget()
            self.sidebar_toggle_btn.configure(text="▶")
            self.sidebar_expanded = False
        else:
            # Expand sidebar
            self.sidebar_frame.configure(width=960)
            self.sidebar.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
            self.sidebar_toggle_btn.configure(text="◀")
            self.sidebar_expanded = True
        self.update_idletasks()

    def search_database(self):
        """Search only the local database without scraping the web"""
        if not self.search_entry.get().strip():
            self.update_status("❌ Please enter a search query!")
            return
            
        self.db_search_btn.configure(state="disabled")
        self.progress.set(0)
        self.update_status("⏳ Searching database...")
        
        # Get all filter values
        content_types = []
        if self.content_types["images"].get(): content_types.append("images")
        if self.content_types["videos"].get(): content_types.append("videos")
        if self.content_types["files"].get(): content_types.append("files")
        if self.content_types["links"].get(): content_types.append("links")
        if self.content_types["text"].get(): content_types.append("text")
        
        # Get advanced filters
        try:
            limit = int(self.limit_entry.get().strip())
        except:
            limit = 10  # Default limit
        
        filters = {
            "content_types": content_types,
            "domain": self.domain_filter.get().strip(),
            "limit": limit,
            "date_range": self.date_options.get(),
            "language": self.language_option.get()
        }
        
        threading.Thread(
            target=self.run_database_search,
            args=(self.search_entry.get(), filters),
            daemon=True
        ).start()
        
    def run_database_search(self, query, filters):
        """Run a search on the local database only"""
        try:
            try:
                from webscraper_o2 import query_database
            except ImportError as e:
                self.log_message(f"Could not import webscraper_o2 module: {str(e)}", "ERROR")
                self.after(0, lambda: self.update_status("❌ Error: Web scraper module not found"))
                return
            
            # Update status and UI
            self.update_status(f"⏳ Searching database for '{query}'...")
            self.log_message(f"Searching database for query: '{query}' with filters: {filters}", "INFO")
            self.after(100, lambda: self.progress.set(0.3))
            
            # Ensure directory structure
            self.ensure_directories()
            
            # Query the database
            search_terms = query.split()
            limit = filters.get("limit", 10)  # Get limit with default
            
            self.log_message(f"Querying database with terms: {search_terms}", "INFO")
            
            results = query_database(
                search_terms=search_terms,
                content_type=filters["content_types"] or None,
                limit=limit
            )

            self.after(100, lambda: self.progress.set(0.7))
            self.current_results = results
            
            # Update UI
            self.after(0, self.clear_results)
            
            if results:
                self.log_message(f"Found {len(results)} results in database", "INFO")
                # Display each result
                for result in results:
                    self.after(0, lambda r=result: self.display_result(r))
            else:
                self.log_message("No results found in database", "WARNING")
                self.after(0, self.show_empty_message)
            
            # Update status
            self.after(100, lambda: (
                self.progress.set(1),
                self.update_status(f"✅ Found {len(results)} results for '{query}' in database!")
            ))
            
        except Exception as e:
            self.log_message(f"Error in database search: {str(e)}", "ERROR")
            self.after(0, lambda err=str(e): self.update_status(f"❌ Error: {err}"))
        finally:
            self.after(0, lambda: self.db_search_btn.configure(state="normal"))

if __name__ == "__main__":
    app = WebScraperGUI()
    app.mainloop()