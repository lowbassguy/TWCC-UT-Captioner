###############################################
#  TWCC Universal Translator - Subtitles App  #
#  Author: Joshua 'lowbass' Sommerfeldt       #
#  (with OpenAI, Whisper, and Tkinter)        #
###############################################

# Core GUI and system imports
import tkinter as tk
from tkinter import ttk, font, messagebox  # ttk for modern widgets, font for text styling, messagebox for dialogs
import threading  # For concurrent audio processing and UI updates
import queue  # Thread-safe communication between audio processing and UI
import time
import os
import json  # For settings file format
import base64  # For encoding encrypted data
import tempfile  # For temporary audio files during processing
import wave  # For audio file creation and manipulation


# Audio processing and AI imports
import whisper  # OpenAI's speech-to-text model
import pyaudio  # Low-level audio capture from microphone
import numpy as np  # Numerical operations for audio data
from cryptography.fernet import Fernet  # Symmetric encryption for API key storage
from openai import OpenAI  # OpenAI API client for translation services
from concurrent.futures import ThreadPoolExecutor  # Thread pool for audio processing

class SettingsDialog:
    """
    Modal dialog window for securely configuring the OpenAI API key.
    
    This dialog provides:
    - Secure input field (password-masked by default)
    - Show/hide toggle for API key visibility
    - Input validation (checks for proper OpenAI key format)
    - Modal behavior (blocks interaction with parent window)
    """
    
    def __init__(self, parent):
        """
        Initialize the settings dialog.
        
        Args:
            parent: The parent tkinter window (main app window)
        """
        self.parent = parent
        self.result = None  # Will store the API key if user saves, None if cancelled
        
        # Create modal dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Settings - API Configuration")
        self.dialog.geometry("400x200")
        self.dialog.resizable(False, False)  # Fixed size for consistent layout
        self.dialog.transient(parent)  # Stay on top of parent window
        self.dialog.grab_set()  # Make dialog modal (blocks parent interaction)
        
        # Center the dialog relative to parent window
        self.dialog.geometry("+%d+%d" % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50))
        
        self.setup_ui()
        
    def setup_ui(self):
        """
        Create and layout all UI elements for the settings dialog.
        
        Layout includes:
        - Title label
        - API key input field (password-masked)
        - Show/hide checkbox
        - Save/Cancel buttons
        - Informational text
        """
        # Main container with padding
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Dialog title
        title_label = ttk.Label(main_frame, text="OpenAI API Configuration", 
                               font=('Arial', 12, 'bold'))
        title_label.pack(pady=(0, 15))
        
        # API Key input section
        ttk.Label(main_frame, text="OpenAI API Key:").pack(anchor=tk.W)
        self.api_key_var = tk.StringVar()  # Variable to hold the API key text
        # Entry field with password masking (show="*")
        self.api_key_entry = ttk.Entry(main_frame, textvariable=self.api_key_var, 
                                      show="*", width=50)
        self.api_key_entry.pack(fill=tk.X, pady=(5, 10))
        
        # Show/Hide API key toggle
        self.show_key = tk.BooleanVar()
        show_check = ttk.Checkbutton(main_frame, text="Show API Key", 
                                    variable=self.show_key, command=self.toggle_key_visibility)
        show_check.pack(anchor=tk.W, pady=(0, 15))
        
        # Button container (right-aligned buttons)
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        # Save and Cancel buttons
        ttk.Button(button_frame, text="Save", command=self.save_settings).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.RIGHT)
        
        # Information label for user guidance
        info_label = ttk.Label(main_frame, text="Your API key will be stored securely on your local machine.", 
                              font=('Arial', 8), foreground='gray')
        info_label.pack(pady=(15, 0))
        
        # Set focus to the input field for immediate typing
        self.api_key_entry.focus()
        
    def toggle_key_visibility(self):
        """
        Toggle API key visibility in the input field.
        When checked: shows plain text
        When unchecked: shows asterisks (password mode)
        """
        if self.show_key.get():
            self.api_key_entry.configure(show="")  # Show plain text
        else:
            self.api_key_entry.configure(show="*")  # Show asterisks
            
    def save_settings(self):
        """
        Validate and save the API key.
        
        Performs validation:
        - Checks if key is not empty
        - Validates OpenAI key format (must start with 'sk-')
        
        If valid, stores key in self.result and closes dialog.
        If invalid, shows error message and keeps dialog open.
        """
        api_key = self.api_key_var.get().strip()
        
        # Validation: empty key
        if not api_key:
            messagebox.showerror("Error", "Please enter your OpenAI API Key")
            return
            
        # Validation: OpenAI key format
        if not api_key.startswith('sk-'):
            messagebox.showerror("Error", "Invalid API Key format. OpenAI keys start with 'sk-'")
            return
            
        # Store result and close dialog
        self.result = api_key
        self.dialog.destroy()
        
    def cancel(self):
        """Close the dialog without saving (result remains None)."""
        self.dialog.destroy()

class SecureSettings:
    """
    Handles secure storage and retrieval of application settings, particularly the OpenAI API key.
    
    Security features:
    - Uses Fernet (symmetric encryption) to encrypt sensitive data
    - Stores files in user's home directory in a hidden folder
    - Generates unique encryption key per installation
    - Base64 encoding for safe file storage
    
    File structure:
    ~/.twcc_captioner/
    ├── config.enc    # Encrypted settings (JSON format)
    └── key.key       # Encryption key (binary)
    """
    
    def __init__(self):
        """
        Initialize the settings manager and create necessary directories.
        
        Sets up file paths:
        - settings_dir: Hidden folder in user's home directory
        - settings_file: Encrypted configuration file
        - key_file: Encryption key file
        """
        # Create settings directory path in user's home folder (hidden folder)
        self.settings_dir = os.path.join(os.path.expanduser("~"), ".twcc_captioner")
        self.settings_file = os.path.join(self.settings_dir, "config.enc")  # Encrypted settings
        self.key_file = os.path.join(self.settings_dir, "key.key")  # Encryption key
        self.ensure_settings_dir()
        
    def ensure_settings_dir(self):
        """Create the settings directory if it doesn't exist."""
        if not os.path.exists(self.settings_dir):
            os.makedirs(self.settings_dir)
            print(f"📁 [SETTINGS] Created settings directory: {self.settings_dir}")
            
    def get_or_create_key(self):
        """
        Get existing encryption key or create a new one.
        
        Returns:
            bytes: The encryption key for Fernet cipher
            
        Note: Each installation gets a unique key, making encrypted files
        non-transferable between different installations (additional security).
        """
        if os.path.exists(self.key_file):
            # Load existing key
            with open(self.key_file, 'rb') as f:
                return f.read()
        else:
            # Generate new key for first-time setup
            key = Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(key)
            print("🔐 [SETTINGS] Generated new encryption key")
            return key
            
    def save_api_key(self, api_key):
        """
        Encrypt and save the OpenAI API key to disk.
        
        Args:
            api_key (str): The OpenAI API key to encrypt and store
            
        Returns:
            bool: True if successful, False if error occurred
            
        Process:
        1. Get/create encryption key
        2. Encrypt the API key using Fernet cipher
        3. Base64 encode the encrypted data for safe JSON storage
        4. Save to encrypted settings file
        """
        try:
            # Get encryption key
            key = self.get_or_create_key()
            cipher = Fernet(key)
            
            # Encrypt the API key
            encrypted_key = cipher.encrypt(api_key.encode())
            
            # Create settings dictionary with base64-encoded encrypted key
            settings = {"api_key": base64.b64encode(encrypted_key).decode()}
            
            # Save to file as JSON
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f)
            print("💾 [SETTINGS] API key saved securely")
            return True
        except Exception as e:
            print(f"❌ [SETTINGS] Error saving API key: {e}")
            return False
            
    def load_api_key(self):
        """
        Load and decrypt the OpenAI API key from disk.
        
        Returns:
            str: The decrypted API key, or None if not found/error
            
        Process:
        1. Check if both settings and key files exist
        2. Load encryption key
        3. Load encrypted settings from JSON
        4. Base64 decode and decrypt the API key
        5. Return decrypted key as string
        """
        try:
            # Check if required files exist
            if not os.path.exists(self.settings_file) or not os.path.exists(self.key_file):
                return None
                
            # Load encryption key
            with open(self.key_file, 'rb') as f:
                key = f.read()
                
            # Load encrypted settings
            with open(self.settings_file, 'r') as f:
                settings = json.load(f)
                
            # Decrypt the API key
            cipher = Fernet(key)
            encrypted_key = base64.b64decode(settings["api_key"].encode())
            api_key = cipher.decrypt(encrypted_key).decode()
            
            print("🔓 [SETTINGS] API key loaded successfully")
            return api_key
        except Exception as e:
            print(f"❌ [SETTINGS] Error loading API key: {e}")
            return None

    def save_ui_preferences(self, bg_color, text_color, font_size, language, recent_languages=None):
        """
        Save UI preferences to local file.
        
        Args:
            bg_color (str): Background color selection
            text_color (str): Text color selection  
            font_size (int): Font size value
            language (str): Selected language
            recent_languages (list): List of recently used languages
            
        Returns:
            bool: True if successful, False if error occurred
        """
        try:
            ui_settings_file = os.path.join(self.settings_dir, "ui_preferences.json")
            
            preferences = {
                "background_color": bg_color,
                "text_color": text_color,
                "font_size": font_size,
                "language": language,
                "recent_languages": recent_languages or []
            }
            
            with open(ui_settings_file, 'w') as f:
                json.dump(preferences, f, indent=2)
            
            print("💾 [SETTINGS] UI preferences saved")
            return True
            
        except Exception as e:
            print(f"❌ [SETTINGS] Error saving UI preferences: {e}")
            return False

    def load_ui_preferences(self):
        """
        Load UI preferences from local file.
        
        Returns:
            dict: Dictionary with UI preference values, or None if not found/error
        """
        try:
            ui_settings_file = os.path.join(self.settings_dir, "ui_preferences.json")
            
            if not os.path.exists(ui_settings_file):
                print("📂 [SETTINGS] No UI preferences file found - using defaults")
                return None
                
            with open(ui_settings_file, 'r') as f:
                preferences = json.load(f)
            
            print("🔓 [SETTINGS] UI preferences loaded successfully")
            return preferences
            
        except Exception as e:
            print(f"❌ [SETTINGS] Error loading UI preferences: {e}")
            return None

class SubtitleApp:
    """
    Main application class for the TWCC Universal Translator.
    
    This application provides real-time speech-to-text transcription with translation
    capabilities for live streaming. It captures audio from the microphone, transcribes
    it using OpenAI's Whisper model, translates it using GPT, and displays the results
    in a customizable overlay window.
    
    Key features:
    - Real-time audio capture and processing
    - Multi-language translation support
    - Customizable overlay window (colors, fonts, positioning)
    - Secure API key management
    - Threaded processing for responsive UI
    
    Architecture:
    - Main UI thread: Handles user interface and display
    - Recording thread: Continuous audio capture
    - Audio processing thread: Whisper transcription
    - Translation thread: GPT formatting and translation
    - Thread-safe queues for communication between components
    """
    
    def __init__(self, root):
        """
        Initialize the main application.
        
        Args:
            root: The main tkinter window
            
        Initialization process:
        1. Set up window properties
        2. Initialize secure settings manager
        3. Load/initialize OpenAI client
        4. Load Whisper model
        5. Configure audio settings
        6. Set up UI components
        7. Start background processing threads
        """
        print("🆕 [INIT] Initializing SubtitleApp 🐣")
        self.root = root
        self.root.title("TWCC Universal Translator - Subtitles")
        self.root.attributes('-topmost', True)  # Keep window on top for streaming overlay
        
        # Initialize secure settings manager
        self.settings = SecureSettings()

        # OpenAI client initialization with settings-based API key
        self.client = None
        self.init_openai_client()

        # Whisper model initialization for speech-to-text
        try:
            print("🎤 [INIT] Loading Whisper model... 🕗")
            # Load base model (good balance of speed vs accuracy for real-time use)
            self.whisper_model = whisper.load_model("base")
            print("✅ [INIT] Whisper model loaded successfully!")
        except Exception as e:
            print(f"❌ [INIT] Failed to load Whisper model: {e}")
            self.whisper_model = None

        # Audio capture configuration
        self.CHUNK = 1024  # Audio buffer size (smaller = more responsive, larger = more efficient)
        self.FORMAT = pyaudio.paInt16  # 16-bit audio format
        self.CHANNELS = 1  # Mono audio (sufficient for speech recognition)
        self.RATE = 16000  # 16kHz sample rate (optimal for Whisper)
        self.RECORD_SECONDS = 3  # Length of each audio chunk for processing
        
        print("🎵 [INIT] Initializing PyAudio 🎶")
        self.audio = pyaudio.PyAudio()  # Audio interface
        
        # Thread-safe queues for inter-thread communication
        self.text_queue = queue.Queue()  # UI updates (processed text to display)
        self.audio_task_queue = queue.Queue()  # Audio chunks for processing
        self.translation_task_queue = queue.Queue()  # Text for translation
        
        # Application state
        self.is_recording = False  # Recording state flag
        
        # Token usage tracking for cost estimation
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        self.session_translations = 0
        
        # Session tracking for reporting
        self.session_start_time = None
        self.session_end_time = None
        
        # Comprehensive language support (based on Google Translate 2024 language list)
        # Dictionary maps display names to language codes for OpenAI API
        self.languages = {
            "Abkhaz": "ab", "Acehnese": "ace", "Acholi": "ach", "Afar": "aa", "Afrikaans": "af",
            "Albanian": "sq", "Alur": "alz", "Amharic": "am", "Arabic": "ar", "Armenian": "hy",
            "Assamese": "as", "Avar": "av", "Awadhi": "awa", "Aymara": "ay", "Azerbaijani": "az",
            "Balinese": "ban", "Baluchi": "bal", "Bambara": "bm", "Baoulé": "bci", "Bashkir": "ba",
            "Basque": "eu", "Batak Karo": "btx", "Batak Simalungun": "bts", "Batak Toba": "bbc",
            "Belarusian": "be", "Bemba": "bem", "Bengali": "bn", "Betawi": "bew", "Bhojpuri": "bho",
            "Bikol": "bik", "Bosnian": "bs", "Breton": "br", "Bulgarian": "bg", "Buryat": "bua",
            "Cantonese": "yue", "Catalan": "ca", "Cebuano": "ceb", "Chamorro": "ch", "Chechen": "ce",
            "Chichewa": "ny", "Chinese (Simplified)": "zh-CN", "Chinese (Traditional)": "zh-TW",
            "Chuukese": "chk", "Chuvash": "cv", "Corsican": "co", "Crimean Tatar": "crh",
            "Croatian": "hr", "Czech": "cs", "Danish": "da", "Dari": "prs", "Dhivehi": "dv",
            "Dinka": "din", "Dogri": "doi", "Dombe": "dov", "Dutch": "nl", "Dyula": "dyu",
            "Dzongkha": "dz", "English": "en", "Esperanto": "eo", "Estonian": "et", "Ewe": "ee",
            "Faroese": "fo", "Fijian": "fj", "Filipino": "fil", "Finnish": "fi", "Fon": "fon",
            "French": "fr", "Friulian": "fur", "Fulani": "ff", "Ga": "gaa", "Galician": "gl",
            "Ganda": "lg", "Georgian": "ka", "German": "de", "Greek": "el", "Guarani": "gn",
            "Gujarati": "gu", "Hakha Chin": "cnh", "Hausa": "ha", "Hawaiian": "haw", "Hebrew": "he",
            "Hiligaynon": "hil", "Hindi": "hi", "Hmong": "hmn", "Hungarian": "hu", "Hunsrik": "hrx",
            "Iban": "iba", "Icelandic": "is", "Igbo": "ig", "Ilocano": "ilo", "Indonesian": "id",
            "Irish": "ga", "Italian": "it", "Jamaican Patois": "jam", "Japanese": "ja", "Javanese": "jv",
            "Jingpo": "kac", "Kalaallisut": "kl", "Kannada": "kn", "Kanuri": "kr", "Kapampangan": "pam",
            "Kashmiri": "ks", "Kazakh": "kk", "Khasi": "kha", "Khmer": "km", "Kiga": "cgg",
            "Kikongo": "kg", "Kinyarwanda": "rw", "Kirghiz": "ky", "Kituba": "ktu", "Kokborok": "trp",
            "Komi": "kv", "Konkani": "gom", "Korean": "ko", "Krio": "kri", "Kurdish (Kurmanji)": "ku",
            "Kurdish (Sorani)": "ckb", "Lao": "lo", "Latgalian": "ltg", "Latin": "la", "Latvian": "lv",
            "Ligurian": "lij", "Limburgish": "li", "Lingala": "ln", "Lithuanian": "lt", "Lombard": "lmo",
            "Luo": "luo", "Luxembourgish": "lb", "Macedonian": "mk", "Madurese": "mad", "Makassar": "mak",
            "Malagasy": "mg", "Malay": "ms", "Malay (Jawi)": "ms-Arab", "Malayalam": "ml", "Maltese": "mt",
            "Manx": "gv", "Maori": "mi", "Marathi": "mr", "Marshallese": "mh", "Marwadi": "mwr",
            "Mauritian Creole": "mfe", "Meadow Mari": "chm", "Meiteilon": "mni", "Minang": "min",
            "Mizo": "lus", "Mongolian": "mn", "Myanmar": "my", "Nahuatl": "nah", "Ndau": "ndc",
            "Ndebele (South)": "nr", "Nepali": "ne", "Nepalbhasa": "new", "NKo": "nqo", "Norwegian": "no",
            "Nuer": "nus", "Occitan": "oc", "Odia": "or", "Oromo": "om", "Ossetian": "os",
            "Pangasinan": "pag", "Papiamento": "pap", "Pashto": "ps", "Persian": "fa", "Polish": "pl",
            "Portuguese": "pt", "Portuguese (Portugal)": "pt-PT", "Punjabi": "pa", "Punjabi (Shahmukhi)": "pa-Arab",
            "Q'eqchi'": "quc", "Quechua": "qu", "Romani": "rom", "Romanian": "ro", "Rundi": "rn",
            "Russian": "ru", "Sami (North)": "se", "Samoan": "sm", "Sango": "sg", "Sanskrit": "sa",
            "Santali": "sat", "Scots Gaelic": "gd", "Serbian": "sr", "Sesotho": "st", "Seychellois Creole": "crs",
            "Shan": "shn", "Shona": "sn", "Sicilian": "scn", "Silesian": "szl", "Sindhi": "sd",
            "Sinhala": "si", "Slovak": "sk", "Slovenian": "sl", "Somali": "so", "Spanish": "es",
            "Sundanese": "su", "Susu": "sus", "Swahili": "sw", "Swati": "ss", "Swedish": "sv",
            "Tahitian": "ty", "Tajik": "tg", "Tamil": "ta", "Tamazight": "tzm", "Tamazight (Tifinagh)": "tzm-Tfng",
            "Tatar": "tt", "Telugu": "te", "Tetum": "tet", "Thai": "th", "Tibetan": "bo",
            "Tigrinya": "ti", "Tiv": "tiv", "Tok Pisin": "tpi", "Tongan": "to", "Tsonga": "ts",
            "Tswana": "tn", "Tulu": "tcy", "Tumbuka": "tum", "Turkish": "tr", "Turkmen": "tk",
            "Tuvan": "tyv", "Twi": "tw", "Udmurt": "udm", "Ukrainian": "uk", "Urdu": "ur",
            "Uyghur": "ug", "Uzbek": "uz", "Venda": "ve", "Venetian": "vec", "Vietnamese": "vi",
            "Waray": "war", "Welsh": "cy", "Wolof": "wo", "Xhosa": "xh", "Yakut": "sah",
            "Yiddish": "yi", "Yoruba": "yo", "Yucatec Maya": "yua", "Zapotec": "zap", "Zulu": "zu"
        }
        self.selected_language = tk.StringVar(value="English")  # Currently selected target language
        self.recent_languages = []  # Track recently used languages (up to 5)
        
        # Set default font family (system fonts only)
        self.font_family = "Arial"
        self.custom_font_loaded = False
        
        print("🖼️ [INIT] Setting up UI 🎨")
        self.setup_ui()
        
        # Load and apply saved UI preferences
        self.load_ui_preferences()
        
        # Start background processing threads
        print("🔁 [INIT] Starting update_text_loop thread ⏩")
        # UI update thread - monitors text queue and updates display
        self.update_thread = threading.Thread(target=self.update_text_loop, daemon=True)
        self.update_thread.start()
        
        print("🧵 [INIT] Starting audio processing thread pool")
        # Thread pool for CPU-intensive audio processing
        self.audio_executor = ThreadPoolExecutor(max_workers=1)
        # Worker thread that monitors audio queue and submits processing jobs
        self.audio_processing_thread = threading.Thread(target=self.audio_worker, daemon=True)
        self.audio_processing_thread.start()
        
        print("🧵 [INIT] Starting translation worker thread")
        # Translation worker thread - handles OpenAI API calls
        self.translation_worker_thread = threading.Thread(target=self.translation_worker, daemon=True)
        self.translation_worker_thread.start()

    def init_openai_client(self):
        """
        Initialize or reinitialize the OpenAI client with the stored API key.
        
        This method is called:
        - During app startup
        - After user saves a new API key in settings
        
        Process:
        1. Load API key from secure storage
        2. Create OpenAI client if key exists
        3. Handle any initialization errors gracefully
        """
        # Load API key from encrypted settings
        api_key = self.settings.load_api_key()
        if api_key:
            try:
                print("🤖 [INIT] Creating OpenAI client ✨")
                self.client = OpenAI(api_key=api_key)
                print("✅ [INIT] OpenAI client created successfully!")
            except Exception as e:
                print(f"❌ [INIT] Failed to create OpenAI client: {e}")
                self.client = None
        else:
            print("❌ [INIT] OpenAI API key not found in settings")



    def create_subtitle_font(self, size):
        """
        Create a subtitle font using system fonts.
        
        Args:
            size (int): Font size
            
        Returns:
            tkinter.font.Font: The created font object
        """
        try:
            # Try Arial first (widely available), then fallback to system default
            subtitle_font = font.Font(family="Arial", size=size, weight="bold")
            print(f"✅ [FONTS] Using Arial font (size: {size})")
            return subtitle_font
        except Exception as e:
            print(f"⚠️ [FONTS] Arial failed, using system default: {e}")
            return font.Font(size=size, weight="bold")

    def show_settings_dialog(self):
        """
        Display the settings dialog for API key configuration.
        
        Process:
        1. Create and show modal settings dialog
        2. Wait for user to save or cancel
        3. If saved, encrypt and store the new API key
        4. Reinitialize OpenAI client with new key
        5. Show success/error feedback to user
        """
        dialog = SettingsDialog(self.root)
        self.root.wait_window(dialog.dialog)  # Block until dialog closes
        
        if dialog.result:  # User clicked Save (not Cancel)
            if self.settings.save_api_key(dialog.result):
                messagebox.showinfo("Success", "API key saved successfully!")
                self.init_openai_client()  # Reinitialize client with new key
            else:
                messagebox.showerror("Error", "Failed to save API key")

    def setup_ui(self):
        """
        Create and layout the main user interface.
        
        UI Components:
        - Control panel: Language selection, recording controls, appearance settings
        - Settings button: For API key configuration
        - Text display area: Large subtitle display with customizable appearance
        
        Layout uses tkinter grid system for responsive design.
        """
        print("🎛️ [UI] Setting up control frame and widgets 🧩")
        
        # Top control panel with all user controls
        control_frame = ttk.Frame(self.root, padding="10")
        control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # Language selection dropdown
        ttk.Label(control_frame, text="Output Language:").grid(row=0, column=0, padx=5)
        self.language_menu = ttk.Combobox(control_frame, textvariable=self.selected_language, 
                                         values=self.get_language_menu_list(), width=35)
        self.language_menu.grid(row=0, column=1, padx=5)
        self.language_menu.bind('<<ComboboxSelected>>', self.on_language_changed)
        
        # Recording start/stop button
        self.record_button = ttk.Button(control_frame, text="Start Recording", 
                                       command=self.toggle_recording)
        self.record_button.grid(row=0, column=2, padx=5)
        
        # Background color selection for subtitle display
        ttk.Label(control_frame, text="Window:").grid(row=0, column=3, padx=5)
        self.bg_color = tk.StringVar(value="black")
        bg_colors = ["black", "green", "blue", "magenta"]  # Colors suitable for overlays
        bg_menu = ttk.Combobox(control_frame, textvariable=self.bg_color, 
                              values=bg_colors, width=10)
        bg_menu.grid(row=0, column=4, padx=5)
        bg_menu.bind('<<ComboboxSelected>>', self.update_background)
        
        # Text color selection for subtitle display
        ttk.Label(control_frame, text="Text:").grid(row=0, column=5, padx=5)
        self.text_color = tk.StringVar(value="white")
        text_colors = ["white", "yellow", "cyan", "red", "green", "orange", "pink"]  # High contrast colors
        text_menu = ttk.Combobox(control_frame, textvariable=self.text_color, 
                                values=text_colors, width=10)
        text_menu.grid(row=0, column=6, padx=5)
        text_menu.bind('<<ComboboxSelected>>', self.update_text_color)
        
        # Font size adjustment for subtitle readability
        ttk.Label(control_frame, text="Font Size:").grid(row=0, column=7, padx=5)
        self.font_size = tk.IntVar(value=24)  # Default size good for streaming
        font_spinner = ttk.Spinbox(control_frame, from_=12, to=48, 
                                  textvariable=self.font_size, width=10,
                                  command=self.update_font)
        font_spinner.grid(row=0, column=8, padx=5)
        
        # Settings button for API key configuration
        settings_button = ttk.Button(control_frame, text="Settings", 
                                   command=self.show_settings_dialog)
        settings_button.grid(row=0, column=9, padx=5)
        
        # Main subtitle display area
        self.text_frame = tk.Frame(self.root, bg="black", height=150)
        self.text_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=10)
        self.text_frame.grid_propagate(False)  # Maintain fixed height
        
        # Subtitle text font configuration
        self.subtitle_font = self.create_subtitle_font(24)
        
        # For streaming overlay - start with blank display (no distracting text)
        initial_text = ""
            
        # Main subtitle label with word wrapping and center alignment
        self.text_label = tk.Label(self.text_frame, text=initial_text, 
                                  fg="white", bg="black", font=self.subtitle_font,
                                  wraplength=780, justify=tk.CENTER)
        self.text_label.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)
        
        # Configure responsive layout
        self.root.columnconfigure(0, weight=1)  # Allow horizontal expansion
        self.root.rowconfigure(1, weight=1)  # Allow subtitle area to expand
        self.root.minsize(800, 250)  # Minimum window size for usability
        print("✅ [UI] UI setup complete! 🥳")

    def update_background(self, event=None):
        """
        Update the background color of the subtitle display area.
        
        Called when user selects a different background color from the dropdown.
        Updates both the frame and label backgrounds to maintain consistency.
        """
        color = self.bg_color.get()
        print(f"🌈 [UI] Background color changed to: {color}")
        self.text_frame.configure(bg=color)
        self.text_label.configure(bg=color)
        # Save preferences when changed
        self.save_ui_preferences()

    def update_text_color(self, event=None):
        """
        Update the text color of the subtitle display.
        
        Called when user selects a different text color from the dropdown.
        Updates the foreground color of the subtitle text.
        """
        color = self.text_color.get()
        print(f"🎨 [UI] Text color changed to: {color}")
        self.text_label.configure(fg=color)
        # Save preferences when changed
        self.save_ui_preferences()

    def update_font(self):
        """
        Update the font size of the subtitle text.
        
        Called when user adjusts the font size spinner.
        Immediately applies the new size to the subtitle display.
        """
        print(f"🔠 [UI] Font size changed to: {self.font_size.get()} px")
        
        # Recreate the font with the new size
        self.subtitle_font = self.create_subtitle_font(self.font_size.get())
        
        # Update the label to use the new font
        self.text_label.configure(font=self.subtitle_font)
        
        # Save preferences when changed
        self.save_ui_preferences()

    def get_language_menu_list(self):
        """
        Generate the language menu list with recent languages, then most common, then alphabetical.
        
        Structure:
        1. Recent languages (last 5 selected)
        2. 20 most commonly spoken world languages
        3. All remaining languages alphabetically
        
        Returns:
            list: Language names in the specified order
        """
        # Get recent languages that are still valid (up to 5)
        valid_recent = [lang for lang in self.recent_languages[:5] if lang in self.languages]
        
        # 20 most commonly spoken languages in the world
        most_common_languages = [
            "Arabic", "Bengali", "Chinese (Simplified)", "English", "French", 
            "German", "Hindi", "Indonesian", "Italian", "Japanese", "Javanese", 
            "Korean", "Malay", "Marathi", "Portuguese", "Punjabi", "Russian", 
            "Spanish", "Tamil", "Turkish"
        ]
        
        # Filter to only include languages that exist in our dictionary and aren't in recent
        valid_common = [lang for lang in most_common_languages 
                       if lang in self.languages and lang not in valid_recent]
        
        # Get all remaining languages alphabetically
        used_languages = set(valid_recent + valid_common)
        remaining_languages = sorted([lang for lang in self.languages.keys() 
                                    if lang not in used_languages])
        
        # Build the final menu list
        menu_list = []
        
        # Add recent languages section
        if valid_recent:
            menu_list.append("--- Recent Languages ---")
            menu_list.extend(valid_recent)
        
        # Add most common languages section
        if valid_common:
            menu_list.append("--- Most Common Languages ---")
            menu_list.extend(valid_common)
        
        # Add remaining languages alphabetically
        if remaining_languages:
            menu_list.append("--- All Other Languages ---")
            menu_list.extend(remaining_languages)
        
        return menu_list

    def update_recent_languages(self, selected_language):
        """
        Update the recent languages list with the newly selected language.
        
        Args:
            selected_language (str): The language that was just selected
        """
        # Skip if it's any separator line
        if selected_language in ["--- Recent Languages ---", "--- Most Common Languages ---", "--- All Other Languages ---"]:
            return
            
        # Remove the language if it's already in the list (to move it to front)
        if selected_language in self.recent_languages:
            self.recent_languages.remove(selected_language)
        
        # Add to the front of the list
        self.recent_languages.insert(0, selected_language)
        
        # Keep only the last 5 recent languages
        self.recent_languages = self.recent_languages[:5]
        
        # Update the dropdown menu values
        self.language_menu.configure(values=self.get_language_menu_list())
        
        print(f"📝 [UI] Recent languages updated: {self.recent_languages}")

    def on_language_changed(self, event=None):
        """
        Handle language selection changes.
        
        Called when user selects a different language from the dropdown.
        Updates recent languages and saves preferences immediately.
        """
        selected = self.selected_language.get()
        
        # Handle separator selections - reset to previous valid selection
        if selected in ["--- Recent Languages ---", "--- Most Common Languages ---", "--- All Other Languages ---"]:
            # Find a valid language to set (first recent, or English, or first common)
            if self.recent_languages:
                self.selected_language.set(self.recent_languages[0])
            elif "English" in self.languages:
                self.selected_language.set("English")
            else:
                # Fallback to first common language
                common_langs = ["Arabic", "Bengali", "Chinese (Simplified)", "English", "French"]
                for lang in common_langs:
                    if lang in self.languages:
                        self.selected_language.set(lang)
                        break
            return
        
        print(f"🌍 [UI] Language changed to: {selected}")
        
        # Update recent languages list
        self.update_recent_languages(selected)
        
        # Save preferences when changed
        self.save_ui_preferences()

    def save_ui_preferences(self):
        """
        Save current UI preferences to settings file.
        """
        self.settings.save_ui_preferences(
            bg_color=self.bg_color.get(),
            text_color=self.text_color.get(),
            font_size=self.font_size.get(),
            language=self.selected_language.get(),
            recent_languages=self.recent_languages
        )

    def load_ui_preferences(self):
        """
        Load and apply saved UI preferences.
        
        Called during app initialization to restore previous settings.
        """
        preferences = self.settings.load_ui_preferences()
        
        if preferences:
            # Apply loaded preferences
            self.bg_color.set(preferences.get("background_color", "black"))
            self.text_color.set(preferences.get("text_color", "white"))
            self.font_size.set(preferences.get("font_size", 24))
            self.selected_language.set(preferences.get("language", "English"))
            
            # Load recent languages
            self.recent_languages = preferences.get("recent_languages", [])
            
            # Update the language menu with recent languages
            self.language_menu.configure(values=self.get_language_menu_list())
            
            # Update UI appearance with loaded settings
            self.update_background()
            self.update_text_color()
            self.update_font()
            
            print(f"✅ [SETTINGS] Applied saved preferences: {preferences.get('background_color')} bg, {preferences.get('text_color')} text, {preferences.get('font_size')}px, {preferences.get('language')}")
            if self.recent_languages:
                print(f"📝 [SETTINGS] Loaded recent languages: {self.recent_languages}")

    def toggle_recording(self):
        """
        Toggle between recording and stopped states.
        
        This is the main control method that starts or stops the entire
        audio capture and processing pipeline.
        """
        print(f"🎙️ [RECORD] Toggle recording. Current state: {self.is_recording}")
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        """
        Start the audio recording and processing pipeline.
        
        Process:
        1. Reset session counters and start tracking
        2. Update UI state (button text, status message)
        3. Set recording flag to True
        4. Start background recording thread
        
        The recording thread will continuously capture audio chunks
        and submit them for processing until stopped.
        """
        print("▶️ [RECORD] Start recording pressed")
        
        # Reset session tracking for new session
        self.session_start_time = time.time()
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        self.session_translations = 0
        print(f"📊 [SESSION] New session started at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        self.is_recording = True
        self.record_button.configure(text="Stop Recording")
        self.text_label.configure(text="")  # Keep overlay clean - no "Listening..." text
        
        # Start recording in separate thread to avoid blocking UI
        self.record_thread = threading.Thread(target=self.record_loop)
        self.record_thread.start()

    def stop_recording(self):
        """
        Stop the audio recording and processing pipeline.
        
        Process:
        1. Set recording flag to False (signals recording thread to stop)
        2. Generate end-of-session report
        3. Update UI state (button text, status message)
        
        The recording thread will finish its current chunk and then exit.
        """
        print("⏹️ [RECORD] Stop recording pressed")
        self.is_recording = False
        
        # Record session end time and generate report
        self.session_end_time = time.time()
        print(f"📊 [SESSION] Session ended at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.generate_session_report()
        
        self.record_button.configure(text="Start Recording")
        self.text_label.configure(text="")  # Clear overlay for clean stream appearance

    def record_loop(self):
        """
        Main audio recording loop (runs in background thread).
        
        This method continuously:
        1. Captures audio from microphone in chunks
        2. Submits complete chunks for processing
        3. Checks recording state to know when to stop
        
        Audio is captured in small buffers (CHUNK size) but processed
        in larger chunks (RECORD_SECONDS worth) for better transcription accuracy.
        """
        print("🎧 [RECORD] Opening audio stream for recording")
        
        # Open audio stream with configured parameters
        stream = self.audio.open(format=self.FORMAT,
                               channels=self.CHANNELS,
                               rate=self.RATE,
                               input=True,  # Input stream (microphone)
                               frames_per_buffer=self.CHUNK)
        
        print("🔴 [RECORD] Recording started...")
        
        while self.is_recording:
            frames = []  # Collect audio frames for this chunk
            
            # Capture RECORD_SECONDS worth of audio
            for i in range(0, int(self.RATE / self.CHUNK * self.RECORD_SECONDS)):
                if not self.is_recording:
                    print("⏸️ [RECORD] Recording interrupted before chunk complete")
                    break
                
                # Read audio data from microphone
                data = stream.read(self.CHUNK, exception_on_overflow=False)
                frames.append(data)
            
            print(f"📼 [RECORD] Collected {len(frames)} frames. is_recording={self.is_recording}")
            
            # Submit complete chunk for processing (if recording is still active)
            if frames and self.is_recording:
                print("🔄 [RECORD] Submitting audio chunk to processing queue")
                self.audio_task_queue.put(frames)
        
        # Clean up audio stream
        stream.stop_stream()
        stream.close()
        print("🛑 [RECORD] Recording stopped.")

    def audio_worker(self):
        """
        Audio processing worker thread.
        
        This thread:
        1. Monitors the audio task queue for new audio chunks
        2. Submits each chunk to the thread pool for processing
        3. Runs continuously until application shutdown
        
        Using a thread pool allows for potentially parallel processing
        of multiple audio chunks if needed in the future.
        """
        print("🛠️ [AUDIO] Audio worker thread started")
        
        while True:
            # Wait for audio chunk from recording thread
            frames = self.audio_task_queue.get()
            
            if frames is None:  # Shutdown signal
                print("🛑 [AUDIO] Audio worker thread exiting")
                break
            
            print("🛠️ [AUDIO] Processing frames from queue")
            # Submit to thread pool for processing
            self.audio_executor.submit(self.process_audio, frames)

    def process_audio(self, frames):
        """
        Process audio chunk through Whisper speech-to-text.
        
        Args:
            frames: List of audio data chunks from microphone
            
        Process:
        1. Check audio level for voice activity detection
        2. Create temporary WAV file from audio frames
        3. Run Whisper transcription on the audio file
        4. Extract text from transcription result
        5. Submit text for translation (if any text was detected)
        6. Clean up temporary file
        
        This method runs in the thread pool to avoid blocking other operations.
        """
        print("🧁 [AUDIO] Processing audio frames...")
        
        # Check if Whisper model is available
        if self.whisper_model is None:
            print("❌ [AUDIO] Whisper model not available. Skipping transcription.")
            return
        
        # Voice Activity Detection - check if audio has sufficient volume
        # Convert audio frames to numpy array for analysis
        audio_data = np.frombuffer(b''.join(frames), dtype=np.int16)
        
        # Calculate RMS (Root Mean Square) volume level
        rms_volume = np.sqrt(np.mean(audio_data.astype(np.float32) ** 2))
        
        # Set threshold for voice activity (adjust this value as needed)
        # Lower values = more sensitive, higher values = less sensitive
        voice_threshold = 500  # Typical speaking volume threshold
        
        print(f"🔊 [AUDIO] Audio RMS level: {rms_volume:.1f} (threshold: {voice_threshold})")
        
        if rms_volume < voice_threshold:
            print("🤫 [AUDIO] Audio level too low - likely silence or background noise. Skipping transcription.")
            return
        
        # Create temporary WAV file for Whisper processing
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            # Set up WAV file with correct audio parameters
            wf = wave.open(tmp_file.name, 'wb')
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(self.audio.get_sample_size(self.FORMAT))
            wf.setframerate(self.RATE)
            wf.writeframes(b''.join(frames))  # Combine all audio chunks
            wf.close()
            
            print(f"📂 [AUDIO] Temporary wav file created: {tmp_file.name}")
            
            try:
                # Run Whisper transcription
                print("🤖 [AUDIO] Calling whisper transcribe...")
                result = self.whisper_model.transcribe(tmp_file.name)
                text = result["text"].strip()  # Extract transcribed text
                print(f"📝 [AUDIO] Whisper transcription: '{text}'")
                
                if text:  # Only process if we got actual text
                    print("🌍 [AUDIO] Sending translation to worker thread")
                    self.translation_task_queue.put(text)
                else:
                    print("🤔 [AUDIO] No transcription text returned")
                    
            except Exception as e:
                print(f"❗Error processing audio: {e}")
            finally:
                # Always clean up temporary file
                print(f"🗑️ [AUDIO] Removing temp file {tmp_file.name}")
                os.remove(tmp_file.name)

    def translation_worker(self):
        """
        Translation worker thread.
        
        This thread:
        1. Monitors the translation task queue for text to process
        2. Formats and translates text using OpenAI GPT
        3. Submits processed text to UI queue for display
        4. Runs continuously until application shutdown
        
        Separating translation into its own thread prevents OpenAI API
        calls from blocking audio processing or UI updates.
        """
        print("🌐 [TRANSLATE] Translation worker thread started")
        
        while True:
            # Wait for text from audio processing
            text = self.translation_task_queue.get()
            
            if text is None:  # Shutdown signal
                print("🛑 [TRANSLATE] Translation worker exiting")
                break
            
            print(f"🌐 [TRANSLATE] Processing text for translation: '{text}'")
            
            # Process text through OpenAI
            translated = self.format_and_translate_sync(text)
            
            if translated:
                print(f"📬 [TRANSLATE] Putting translated text in UI queue: '{translated}'")
                self.text_queue.put(translated)  # Send to UI for display
            else:
                print("😿 [TRANSLATE] No translated text returned")

    def format_and_translate_sync(self, text):
        """
        Format and translate text using OpenAI GPT.
        
        Args:
            text (str): Raw transcribed text from Whisper
            
        Returns:
            str: Formatted and translated text, or original text if error
            
        Process:
        1. Check if OpenAI client is available
        2. Determine target language from user selection
        3. Create appropriate prompt (format-only for English, translate for others)
        4. Call OpenAI API with optimized parameters
        5. Return processed text
        
        For English: Only formats (fixes capitalization, punctuation, spelling)
        For other languages: Formats AND translates to target language
        """
        # Check if OpenAI client is available
        if self.client is None:
            print("❌ [TRANSLATE] OpenAI client not available. Returning original text.")
            return text
            
        # Get target language code
        target_lang = self.languages[self.selected_language.get()]
        print(f"🌐 [TRANSLATE] Formatting/translating to {self.selected_language.get()} ({target_lang})")
        
        try:
            # Create prompt based on target language
            if target_lang == "en":
                # English: format and correct only
                prompt = f"Format the following transcribed text with proper capitalization, punctuation, and spelling corrections. Keep the meaning exactly the same:\n\n{text}"
            else:
                # Other languages: format and translate
                prompt = f"Format the following transcribed text with proper capitalization, punctuation, and spelling corrections, then translate it to {self.selected_language.get()}. Use informal, conversational language appropriate for live streaming. Return only the translated text, nothing else:\n\n{text}"
            
            print(f"📤 [TRANSLATE] Prompt sent to OpenAI: {prompt[:100]}{'...' if len(prompt)>100 else ''}")
            
            # Call OpenAI API with optimized parameters
            response = self.client.chat.completions.create(
                model="gpt-4.1-nano",  # Fast, cost-effective model for real-time use
                messages=[
                    {"role": "system", "content": "You are a professional translator and editor who specializes in informal, conversational translations for live streaming."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Low temperature for consistent, accurate translations
                max_tokens=200  # Limit response length for subtitle use
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Log token usage and calculate costs
            self.log_token_usage(response)
            
            print(f"💌 [TRANSLATE] Received translation: '{result_text}'")
            return result_text
            
        except Exception as e:
            print(f"❗Error in formatting/translation: {e}")
            return text  # Return original text if translation fails

    def log_token_usage(self, response):
        """
        Log token usage and calculate cost estimation for OpenAI API calls.
        
        Args:
            response: OpenAI API response object containing usage statistics
            
        GPT-4.1 nano pricing (per 1M tokens):
        - Input tokens: $0.10
        - Output tokens: $0.40
        - Cached input: $0.025 (not tracked separately for simplicity)
        """
        try:
            # Extract token usage from API response
            usage = response.usage
            input_tokens = usage.prompt_tokens
            output_tokens = usage.completion_tokens
            total_tokens = usage.total_tokens
            
            # Calculate costs (convert from per-million to per-token rates)
            input_cost = (input_tokens / 1_000_000) * 0.10  # $0.10 per 1M input tokens
            output_cost = (output_tokens / 1_000_000) * 0.40  # $0.40 per 1M output tokens
            total_cost = input_cost + output_cost
            
            # Update session totals
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            self.total_cost += total_cost
            self.session_translations += 1
            
            # Log current API call details
            print(f"💰 [COST] Translation #{self.session_translations}")
            print(f"💰 [COST] Input: {input_tokens} tokens (${input_cost:.6f})")
            print(f"💰 [COST] Output: {output_tokens} tokens (${output_cost:.6f})")
            print(f"💰 [COST] This call: ${total_cost:.6f}")
            
            # Log session totals
            print(f"💰 [COST] === SESSION TOTALS ===")
            print(f"💰 [COST] Total translations: {self.session_translations}")
            print(f"💰 [COST] Total input tokens: {self.total_input_tokens:,}")
            print(f"💰 [COST] Total output tokens: {self.total_output_tokens:,}")
            print(f"💰 [COST] Total session cost: ${self.total_cost:.6f}")
            
            # Cost per translation average
            avg_cost = self.total_cost / self.session_translations if self.session_translations > 0 else 0
            print(f"💰 [COST] Average cost per translation: ${avg_cost:.6f}")
            print(f"💰 [COST] ========================")
            
        except Exception as e:
            print(f"❗Error logging token usage: {e}")

    def generate_session_report(self):
        """
        Generate and save a detailed session report to file.
        
        Creates a timestamped text file with comprehensive session statistics
        including duration, token usage, costs, and efficiency metrics.
        """
        try:
            # Skip report generation if no session data
            if self.session_start_time is None or self.session_end_time is None:
                print("⚠️ [SESSION] No session data available for report generation")
                return
            
            # Calculate session duration
            duration_seconds = self.session_end_time - self.session_start_time
            duration_minutes = duration_seconds / 60
            duration_str = f"{int(duration_minutes)} minutes {int(duration_seconds % 60)} seconds"
            
            # Create expense reports directory if it doesn't exist
            reports_dir = "expense_reports"
            if not os.path.exists(reports_dir):
                os.makedirs(reports_dir)
                print(f"📁 [SESSION] Created expense reports directory: {reports_dir}")
            
            # Generate timestamp for filename
            timestamp = time.strftime('%Y-%m-%d_%H-%M-%S', time.localtime(self.session_start_time))
            filename = os.path.join(reports_dir, f"session_report_{timestamp}.txt")
            
            # Calculate efficiency metrics
            translations_per_minute = self.session_translations / duration_minutes if duration_minutes > 0 else 0
            avg_tokens_per_translation = (self.total_input_tokens + self.total_output_tokens) / self.session_translations if self.session_translations > 0 else 0
            cost_per_minute = self.total_cost / duration_minutes if duration_minutes > 0 else 0
            projected_hourly_cost = cost_per_minute * 60
            
            # Generate report content
            report_content = f"""=== TWCC Translation Session Report ===
Session Date: {time.strftime('%Y-%m-%d', time.localtime(self.session_start_time))}
Start Time: {time.strftime('%H:%M:%S', time.localtime(self.session_start_time))}
End Time: {time.strftime('%H:%M:%S', time.localtime(self.session_end_time))}
Duration: {duration_str}

TRANSLATION STATS:
- Total Translations: {self.session_translations}
- Target Language: {self.selected_language.get()}
- Translations per minute: {translations_per_minute:.1f}

TOKEN USAGE:
- Total Input Tokens: {self.total_input_tokens:,}
- Total Output Tokens: {self.total_output_tokens:,}
- Total Tokens: {(self.total_input_tokens + self.total_output_tokens):,}

COST BREAKDOWN:
- Input Cost: ${(self.total_input_tokens / 1_000_000) * 0.10:.6f}
- Output Cost: ${(self.total_output_tokens / 1_000_000) * 0.40:.6f}
- Total Session Cost: ${self.total_cost:.6f}
- Average Cost per Translation: ${(self.total_cost / self.session_translations if self.session_translations > 0 else 0):.6f}

EFFICIENCY METRICS:
- Tokens per translation (avg): {avg_tokens_per_translation:.1f}
- Cost per minute: ${cost_per_minute:.6f}
- Projected hourly cost: ${projected_hourly_cost:.6f}

=== End of Report ===
"""
            
            # Write report to file
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            print(f"📄 [SESSION] Session report saved to: {filename}")
            print(f"📊 [SESSION] Summary: {self.session_translations} translations, ${self.total_cost:.6f} total cost")
            
        except Exception as e:
            print(f"❗Error generating session report: {e}")

    def update_text_loop(self):
        """
        UI update loop (runs in background thread).
        
        This thread:
        1. Monitors the text queue for new processed text
        2. Updates the subtitle display when new text arrives
        3. Uses tkinter's thread-safe after() method for UI updates
        4. Runs continuously until application shutdown
        
        This separation ensures UI updates don't block audio processing
        and provides smooth, responsive subtitle display.
        """
        print("⏳ [THREAD] update_text_loop started")
        
        while True:
            try:
                # Wait for new text with short timeout
                text = self.text_queue.get(timeout=0.1)
                print(f"📨 [THREAD] Got text from queue: '{text}'")
                
                # Schedule UI update on main thread (thread-safe)
                self.root.after(0, lambda t=text: self.text_label.configure(text=t))
                
            except queue.Empty:
                # Timeout is normal - continue loop
                pass
            except Exception as e:
                print(f"❗Error updating text: {e}")

    def cleanup(self):
        """
        Clean up resources and shut down background threads.
        
        Called when application is closing to ensure:
        1. Audio recording is stopped
        2. PyAudio resources are released
        3. Background threads are signaled to exit
        4. Thread pools are shut down properly
        
        This prevents resource leaks and ensures clean application shutdown.
        """
        print("🧹 [CLEANUP] Cleaning up, terminating PyAudio 📴")
        
        # Stop recording
        self.is_recording = False
        
        # Terminate audio system
        self.audio.terminate()
        
        # Shut down audio worker and thread pool
        self.audio_task_queue.put(None)  # Send shutdown signal
        self.audio_executor.shutdown(wait=False)
        
        # Shut down translation worker
        self.translation_task_queue.put(None)  # Send shutdown signal


def main():
    """
    Application entry point.
    
    Creates the main tkinter window, initializes the SubtitleApp,
    sets up proper cleanup on window close, and starts the main event loop.
    """
    print("🚀 [MAIN] Starting app")
    
    # Create main window
    root = tk.Tk()
    
    # Initialize application
    app = SubtitleApp(root)
    
    # Set up proper cleanup when window is closed
    root.protocol("WM_DELETE_WINDOW", lambda: [app.cleanup(), root.destroy()])
    
    # Start main event loop
    root.mainloop()

if __name__ == "__main__":
    main()
