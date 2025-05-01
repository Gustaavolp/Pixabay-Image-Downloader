import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import os
from pathlib import Path
import logging
import time

# Importar scraper após modificações
from pixabay_utils import scraper

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(message)s'
)

# Available options from Pixabay API
IMAGE_TYPES = ["photo", "illustration", "vector", "all"]
ORIENTATIONS = ["all", "horizontal", "vertical"]
CATEGORIES = [
    "", "backgrounds", "fashion", "nature", "science", "education", 
    "feelings", "health", "people", "religion", "places", "animals", 
    "industry", "computer", "food", "sports", "transportation", 
    "travel", "buildings", "business", "music"
]
COLOR_OPTIONS = [
    "grayscale", "transparent", "red", "orange", "yellow", "green", 
    "turquoise", "blue", "lilac", "pink", "white", "gray", "black", "brown"
]
ORDER_OPTIONS = ["popular", "latest"]
LANG_OPTIONS = [
    "cs", "da", "de", "en", "es", "fr", "id", "it", "hu", "nl", 
    "no", "pl", "pt", "ro", "sk", "fi", "sv", "tr", "vi", "th", 
    "bg", "ru", "el", "ja", "ko", "zh"
]
FILE_TYPES = ["jpg", "png"]

# Create a custom scraper function that reports progress
def progress_scraper(api_key, img_classes, path, images, image_type, orientation, 
                    category, min_width, min_height, colors, editors_choice, 
                    safesearch, order, lang, file_type, progress_callback=None):
    """Wrapper around the scraper function to report progress"""
    
    # First, count the total number of images to download
    total_images = len(img_classes) * images
    current_count = 0
    
    # Create a list to store the actual number of images we'll download
    # (might be less than requested if not enough are available)
    actual_total = 0
    
    # Define a progress callback
    def count_callback(current_class, class_idx, img_count):
        nonlocal current_count, actual_total
        # Update our count and report to the progress callback
        if progress_callback:
            current_count = class_idx * images + img_count
            # We need to report a value between 0 and 1 representing percentage
            progress_callback(current_count, total_images, current_class)
    
    # Call the actual scraper with our callback
    result = scraper(api_key, img_classes, path, images, image_type, orientation, 
                     category, min_width, min_height, colors, editors_choice, 
                     safesearch, order, lang, file_type, progress_callback=count_callback)
    
    return result

class ToolTip:
    """Create a tooltip for a given widget"""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)
    
    def show_tooltip(self, event=None):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        
        # Create a toplevel window
        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        
        # Create a label in the toplevel window
        label = tk.Label(self.tooltip_window, text=self.text, 
                         justify=tk.LEFT, background="#ffffe0", 
                         relief=tk.SOLID, borderwidth=1)
        label.pack(padx=3, pady=3)
    
    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

class PixabayImageDownloader:
    def __init__(self, root):
        self.root = root
        self.root.title("Pixabay Image Downloader - Bulk Image Retrieval Tool")
        self.root.geometry("900x750")
        self.root.minsize(800, 700)  # Define tamanho mínimo da janela
        
        # Create a main frame that will contain everything
        self.main_container = tk.Frame(root)
        self.main_container.pack(fill=tk.BOTH, expand=True)
        
        # Fixed height button frame that will always be visible
        # Using a simpler style for the button area
        self.button_frame = tk.Frame(self.main_container, height=60)
        self.button_frame.pack(side=tk.BOTTOM, fill=tk.X)
        # Force the height to remain fixed
        self.button_frame.pack_propagate(False)
        
        # Content frame for everything else
        self.content_frame = ttk.Frame(self.main_container)
        self.content_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create a notebook (tabs) inside content frame
        self.notebook = ttk.Notebook(self.content_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Main tab
        self.main_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.main_tab, text="Main Settings")
        
        # Advanced tab
        self.advanced_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.advanced_tab, text="Advanced Settings")
        
        # Log tab
        self.log_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.log_tab, text="Log")
        
        # Help tab
        self.help_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.help_tab, text="Help")
        
        # Set up main tab
        self.setup_main_tab()
        
        # Set up advanced tab
        self.setup_advanced_tab()
        
        # Set up log tab
        self.setup_log_tab()
        
        # Set up help tab
        self.setup_help_tab()
        
        # Progress indicators frame
        self.progress_frame = ttk.LabelFrame(self.content_frame, text="Download Progress")
        self.progress_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5)
        self.setup_progress_indicators()
        
        # Download button - more subtle styling
        self.download_button = tk.Button(
            self.button_frame,
            text="Download Images",
            command=self.start_download,
            font=("Arial", 10),
            width=15,
            height=1,
            cursor="hand2"
        )
        self.download_button.pack(side=tk.RIGHT, padx=20, pady=10)
        
        # Variables for tracking download progress
        self.downloading = False
        self.download_thread = None
        
        # Try to load API key from secrets.py if available
        try:
            from secrets import api_key
            if api_key:
                self.api_key_var.set(api_key)
                logger.info("Loaded API key from secrets.py")
        except ImportError:
            pass
    
    def setup_main_tab(self):
        # Create a frame for the form
        form_frame = ttk.Frame(self.main_tab)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # API Key
        ttk.Label(form_frame, text="API Key (required):", font=("", 10, "bold")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.api_key_var = tk.StringVar()
        api_key_entry = ttk.Entry(form_frame, textvariable=self.api_key_var, width=50)
        api_key_entry.grid(row=0, column=1, sticky=tk.W)
        ToolTip(api_key_entry, "Your Pixabay API key from https://pixabay.com/api/docs/")
        
        # Add a link to get API key
        api_link = ttk.Label(form_frame, text="Get API Key", foreground="blue", cursor="hand2")
        api_link.grid(row=0, column=2, padx=5)
        api_link.bind("<Button-1>", lambda e: self.open_url("https://pixabay.com/api/docs/"))
        
        # Search Terms Frame with explanation
        search_frame = ttk.LabelFrame(form_frame, text="Search Terms (required)")
        search_frame.grid(row=1, column=0, columnspan=3, sticky=tk.W+tk.E, pady=10, padx=5)
        
        # Add detailed explanation
        ttk.Label(search_frame, text="Enter the terms to search for images. You can search for multiple terms at once by separating them with commas.", 
                  wraplength=600).grid(row=0, column=0, columnspan=3, sticky=tk.W, padx=5, pady=5)
        
        # Simple search input (single line, comma separated)
        self.search_terms_var = tk.StringVar()
        self.search_terms_entry = ttk.Entry(search_frame, textvariable=self.search_terms_var, width=70)
        self.search_terms_entry.grid(row=2, column=0, columnspan=3, sticky=tk.W+tk.E, padx=5, pady=5)
        ToolTip(self.search_terms_entry, "Enter search terms separated by commas\nExample: sunset, mountains, beach")
        
        # Examples
        ttk.Label(search_frame, text="Examples:", font=("", 9, "italic")).grid(row=4, column=0, sticky=tk.W, padx=5)
        ttk.Label(search_frame, text="nature, beach sunset, red roses, cats, dogs").grid(row=4, column=1, columnspan=2, sticky=tk.W)
        
        # Save Path
        ttk.Label(form_frame, text="Save Directory:", font=("", 10, "bold")).grid(row=2, column=0, sticky=tk.W, pady=10)
        self.save_path_var = tk.StringVar(value=os.path.join(os.getcwd(), "images"))
        save_path_entry = ttk.Entry(form_frame, textvariable=self.save_path_var, width=50)
        save_path_entry.grid(row=2, column=1, sticky=tk.W)
        ttk.Button(form_frame, text="Browse...", command=self.browse_directory).grid(row=2, column=2, sticky=tk.W)
        
        # Number of images
        ttk.Label(form_frame, text="Images per term:", font=("", 10, "bold")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.num_images_var = tk.IntVar(value=10)
        images_spin = ttk.Spinbox(form_frame, from_=1, to=200, textvariable=self.num_images_var, width=10)
        images_spin.grid(row=3, column=1, sticky=tk.W)
        ToolTip(images_spin, "Number of images to download for each search term")
        
        # Image type
        ttk.Label(form_frame, text="Image Type:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.image_type_var = tk.StringVar(value="photo")
        image_type_combo = ttk.Combobox(form_frame, textvariable=self.image_type_var, values=IMAGE_TYPES, width=15, state="readonly")
        image_type_combo.grid(row=4, column=1, sticky=tk.W)
        ToolTip(image_type_combo, "Type of images to download:\n- photo: Real photographs\n- illustration: Digital illustrations\n- vector: Vector graphics\n- all: All types")
        
        # Orientation
        ttk.Label(form_frame, text="Orientation:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.orientation_var = tk.StringVar(value="all")
        orientation_combo = ttk.Combobox(form_frame, textvariable=self.orientation_var, values=ORIENTATIONS, width=15, state="readonly")
        orientation_combo.grid(row=5, column=1, sticky=tk.W)
        ToolTip(orientation_combo, "Filter images by orientation:\n- horizontal: Landscape orientation\n- vertical: Portrait orientation\n- all: Both orientations")
        
        # File type
        ttk.Label(form_frame, text="File Type:").grid(row=6, column=0, sticky=tk.W, pady=5)
        self.file_type_var = tk.StringVar(value="jpg")
        file_type_combo = ttk.Combobox(form_frame, textvariable=self.file_type_var, values=FILE_TYPES, width=15, state="readonly")
        file_type_combo.grid(row=6, column=1, sticky=tk.W)
        ToolTip(file_type_combo, "Format to save the downloaded images")
    
    def open_url(self, url):
        # Open URL in default browser
        import webbrowser
        webbrowser.open(url)
    
    def setup_advanced_tab(self):
        # Create a frame for the form
        form_frame = ttk.Frame(self.advanced_tab)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Category
        ttk.Label(form_frame, text="Category:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.category_var = tk.StringVar(value="")
        category_combo = ttk.Combobox(form_frame, textvariable=self.category_var, values=CATEGORIES, width=15, state="readonly")
        category_combo.grid(row=0, column=1, sticky=tk.W)
        ToolTip(category_combo, "Filter images by category such as nature, people, etc.")
        
        # Minimum dimensions
        ttk.Label(form_frame, text="Minimum Width:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.min_width_var = tk.IntVar(value=0)
        min_width_spin = ttk.Spinbox(form_frame, from_=0, to=10000, textvariable=self.min_width_var, width=10)
        min_width_spin.grid(row=1, column=1, sticky=tk.W)
        ToolTip(min_width_spin, "Minimum width of images in pixels (0 = no minimum)")
        
        ttk.Label(form_frame, text="Minimum Height:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.min_height_var = tk.IntVar(value=0)
        min_height_spin = ttk.Spinbox(form_frame, from_=0, to=10000, textvariable=self.min_height_var, width=10)
        min_height_spin.grid(row=2, column=1, sticky=tk.W)
        ToolTip(min_height_spin, "Minimum height of images in pixels (0 = no minimum)")
        
        # Colors
        ttk.Label(form_frame, text="Colors:").grid(row=3, column=0, sticky=tk.W, pady=5)
        colors_frame = ttk.Frame(form_frame)
        colors_frame.grid(row=3, column=1, sticky=tk.W)
        
        self.color_vars = {}
        col = 0
        row = 0
        for color in COLOR_OPTIONS:
            self.color_vars[color] = tk.BooleanVar(value=False)
            cb = ttk.Checkbutton(colors_frame, text=color, variable=self.color_vars[color])
            cb.grid(row=row, column=col, sticky=tk.W, padx=5)
            col += 1
            if col > 3:
                col = 0
                row += 1
        
        ToolTip(colors_frame, "Filter images by color properties.\nSelect multiple colors to find images containing any of the selected colors.")
        
        # Editor's Choice
        ttk.Label(form_frame, text="Editor's Choice:").grid(row=8, column=0, sticky=tk.W, pady=5)
        self.editors_choice_var = tk.BooleanVar(value=False)
        editors_cb = ttk.Checkbutton(form_frame, variable=self.editors_choice_var)
        editors_cb.grid(row=8, column=1, sticky=tk.W)
        ToolTip(editors_cb, "Only include images that have received an Editor's Choice award")
        
        # Safe Search
        ttk.Label(form_frame, text="Safe Search:").grid(row=9, column=0, sticky=tk.W, pady=5)
        self.safesearch_var = tk.BooleanVar(value=True)
        safe_cb = ttk.Checkbutton(form_frame, variable=self.safesearch_var)
        safe_cb.grid(row=9, column=1, sticky=tk.W)
        ToolTip(safe_cb, "Filter out content that might not be suitable for all ages")
        
        # Order
        ttk.Label(form_frame, text="Order:").grid(row=10, column=0, sticky=tk.W, pady=5)
        self.order_var = tk.StringVar(value="popular")
        order_combo = ttk.Combobox(form_frame, textvariable=self.order_var, values=ORDER_OPTIONS, width=15, state="readonly")
        order_combo.grid(row=10, column=1, sticky=tk.W)
        ToolTip(order_combo, "Sort results by:\n- popular: Most popular images first\n- latest: Most recent images first")
        
        # Language
        ttk.Label(form_frame, text="Language:").grid(row=11, column=0, sticky=tk.W, pady=5)
        self.lang_var = tk.StringVar(value="en")
        lang_combo = ttk.Combobox(form_frame, textvariable=self.lang_var, values=LANG_OPTIONS, width=15, state="readonly")
        lang_combo.grid(row=11, column=1, sticky=tk.W)
        ToolTip(lang_combo, "Language code of the language to be searched in")
    
    def setup_log_tab(self):
        # Create a frame for the log
        log_frame = ttk.Frame(self.log_tab)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Log text widget
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, width=80, height=20)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Create a handler to redirect log messages to the text widget
        class TextHandler(logging.Handler):
            def __init__(self, text_widget):
                logging.Handler.__init__(self)
                self.text_widget = text_widget
            
            def emit(self, record):
                msg = self.format(record)
                def append():
                    self.text_widget.configure(state='normal')
                    self.text_widget.insert(tk.END, msg + '\n')
                    self.text_widget.configure(state='disabled')
                    self.text_widget.see(tk.END)
                # This is necessary because the append may be called from a non-main thread
                self.text_widget.after(0, append)
        
        # Add the handler to the logger
        text_handler = TextHandler(self.log_text)
        text_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        logger.addHandler(text_handler)
        
        # Make the text widget read-only
        self.log_text.configure(state='disabled')
    
    def setup_help_tab(self):
        # Create a frame for the help content
        help_frame = ttk.Frame(self.help_tab)
        help_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Help text
        help_text = (
            "# Pixabay Image Downloader - Bulk Image Retrieval Tool\n\n"
            "## Quick Start\n"
            "1. Enter your Pixabay API key (get one at https://pixabay.com/api/docs/)\n"
            "2. Enter one or more search terms separated by commas\n"
            "3. Set the number of images to download per term\n"
            "4. Click 'Download Images'\n\n"
            
            "## Search Terms\n"
            "You can enter multiple search terms to download different categories of images.\n\n"
            "Enter terms separated by commas:\n"
            "Example: sunset, mountains, beach, dogs, cats\n\n"
            "Each term will be searched separately, and the specified number of images will be\n"
            "downloaded for each term into separate folders.\n\n"
            
            "## Advanced Options\n"
            "- **Image Type**: Choose between photos, illustrations, or vector graphics\n"
            "- **Orientation**: Filter by landscape or portrait orientation\n"
            "- **Category**: Filter images by predefined categories\n"
            "- **Colors**: Filter images by dominant colors\n"
            "- **Editor's Choice**: Only include high-quality images selected by Pixabay editors\n"
            "- **Safe Search**: Filter out adult content\n\n"
            
            "## Tips\n"
            "- Be specific with your search terms for better results\n"
            "- Use the Advanced Settings tab to refine your search\n"
            "- Check the Log tab to monitor the download progress\n"
            "- Your API key can be stored in a secrets.py file for convenience\n\n"
            
            "## About\n"
            "Pixabay Image Downloader is an open-source tool for downloading images from Pixabay.\n"
            "All images are subject to the Pixabay Content License:\n"
            "https://pixabay.com/service/license/\n"
        )
        
        # Help text widget
        help_text_widget = scrolledtext.ScrolledText(help_frame, wrap=tk.WORD, width=80, height=30)
        help_text_widget.pack(fill=tk.BOTH, expand=True)
        help_text_widget.insert(tk.END, help_text)
        help_text_widget.configure(state='disabled')
    
    def setup_progress_indicators(self):
        """Set up progress indicators in the progress frame"""
        # Current term and count
        info_frame = ttk.Frame(self.progress_frame)
        info_frame.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Label(info_frame, text="Current term:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.current_term_var = tk.StringVar(value="-")
        ttk.Label(info_frame, textvariable=self.current_term_var).grid(row=0, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(info_frame, text="Total Progress:").grid(row=1, column=0, sticky=tk.W, padx=5)
        self.progress_count_var = tk.StringVar(value="0/0")
        ttk.Label(info_frame, textvariable=self.progress_count_var).grid(row=1, column=1, sticky=tk.W, padx=5)
        
        # Progress bar
        self.progress = ttk.Progressbar(self.progress_frame, mode='determinate', length=100)
        self.progress.pack(fill=tk.X, padx=5, pady=5)
        
        # Status label
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(self.progress_frame, textvariable=self.status_var)
        status_label.pack(anchor=tk.W, pady=5)
    
    def browse_directory(self):
        directory = filedialog.askdirectory(initialdir=self.save_path_var.get())
        if directory:
            self.save_path_var.set(directory)
    
    def get_selected_colors(self):
        selected_colors = [color for color, var in self.color_vars.items() if var.get()]
        if selected_colors:
            return ",".join(selected_colors)
        return None
    
    def get_search_terms(self):
        # Get terms from the entry field
        return [term.strip() for term in self.search_terms_var.get().split(",") if term.strip()]
    
    def validate_inputs(self):
        # Check required fields
        if not self.api_key_var.get().strip():
            messagebox.showerror("Error", "API Key is required")
            return False
        
        search_terms = self.get_search_terms()
        if not search_terms:
            messagebox.showerror("Error", "At least one search term is required")
            return False
        
        return True
    
    def update_progress(self, current, total, current_term):
        """Update the progress bar and status"""
        # Calculate the progress percentage correctly based on downloaded images
        progress_value = (current/total*100) if total > 0 else 0
        self.root.after(0, lambda: self.progress.configure(value=progress_value))
        self.root.after(0, lambda: self.current_term_var.set(current_term))
        self.root.after(0, lambda: self.progress_count_var.set(f"{current}/{total}"))
        self.root.after(0, lambda: self.status_var.set(f"Downloading {current_term}... {int(progress_value)}%"))
    
    def start_download(self):
        if self.downloading:
            messagebox.showinfo("Info", "Download already in progress")
            return
        
        if not self.validate_inputs():
            return
        
        # Get the search terms
        search_terms = self.get_search_terms()
        
        # Start progress display
        self.progress.configure(value=0)
        self.current_term_var.set("Starting...")
        self.progress_count_var.set("0/0")
        self.status_var.set("Downloading...")
        self.downloading = True
        
        # Prepare parameters
        api_key = self.api_key_var.get().strip()
        save_path = self.save_path_var.get()
        num_images = self.num_images_var.get()
        
        # Get all the other parameters
        image_type = self.image_type_var.get()
        orientation = self.orientation_var.get()
        category = self.category_var.get() if self.category_var.get() else None
        min_width = self.min_width_var.get()
        min_height = self.min_height_var.get()
        colors = self.get_selected_colors()
        editors_choice = self.editors_choice_var.get()
        safesearch = self.safesearch_var.get()
        order = self.order_var.get()
        lang = self.lang_var.get()
        file_type = self.file_type_var.get()
        
        # Log the parameters
        logger.info(f"Starting download with the following parameters:")
        logger.info(f"Search terms: {search_terms}")
        logger.info(f"Save path: {save_path}")
        logger.info(f"Number of images per term: {num_images}")
        logger.info(f"Image type: {image_type}")
        logger.info(f"Orientation: {orientation}")
        if category:
            logger.info(f"Category: {category}")
        logger.info(f"Min dimensions: {min_width}x{min_height}")
        if colors:
            logger.info(f"Colors: {colors}")
        logger.info(f"Editor's choice: {editors_choice}")
        logger.info(f"Safe search: {safesearch}")
        logger.info(f"Order: {order}")
        logger.info(f"Language: {lang}")
        logger.info(f"File type: {file_type}")
        
        # Create a thread to run the download
        self.download_thread = threading.Thread(
            target=self.run_download, 
            args=(api_key, search_terms, save_path, num_images, image_type, 
                  orientation, category, min_width, min_height, colors, 
                  editors_choice, safesearch, order, lang, file_type)
        )
        self.download_thread.daemon = True
        self.download_thread.start()
    
    def run_download(self, api_key, search_terms, save_path, num_images, image_type, orientation, 
                    category, min_width, min_height, colors, editors_choice, safesearch, 
                    order, lang, file_type):
        try:
            # Run the scraper with progress
            total_downloaded = progress_scraper(
                api_key, search_terms, save_path, num_images, image_type, orientation, 
                category, min_width, min_height, colors, editors_choice, 
                safesearch, order, lang, file_type, 
                progress_callback=self.update_progress
            )
            
            # Show completion message
            self.root.after(0, lambda: self.status_var.set(f"Download complete. Downloaded {total_downloaded} images."))
            self.root.after(0, lambda: messagebox.showinfo("Success", f"Downloaded {total_downloaded} images."))
            
        except Exception as e:
            logger.error(f"Download failed: {e}")
            self.root.after(0, lambda: self.status_var.set("Download failed. See log for details."))
            self.root.after(0, lambda: messagebox.showerror("Error", f"Download failed: {e}"))
        
        finally:
            # Reset UI state
            self.downloading = False
    
    def cancel_download(self):
        # This method is no longer used, but we'll keep it for future reference
        pass

if __name__ == "__main__":
    root = tk.Tk()
    app = PixabayImageDownloader(root)
    root.mainloop() 