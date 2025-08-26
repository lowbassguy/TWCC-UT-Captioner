#!/usr/bin/env python3
"""
Build script for creating a standalone Windows executable of TWCC Captioner.
This script uses PyInstaller to bundle the application with all dependencies.
"""

import subprocess
import sys
import os
import shutil
from pathlib import Path

def install_build_dependencies():
    """Install PyInstaller if not already installed."""
    print("Installing build dependencies...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    print("Build dependencies installed!")

def create_spec_file():
    """Create a PyInstaller spec file with custom configuration if it doesn't exist."""
    
    # Check if spec file already exists
    if os.path.exists('captioner.spec'):
        print("Found existing captioner.spec file - preserving it")
        return
    
    print("Creating new PyInstaller spec file...")
    
    # First create the runtime hook file
    runtime_hook_content = '''
import os
import sys

# Set environment variables for Whisper model caching
# This ensures models are stored in user's home directory where we have write access
if getattr(sys, 'frozen', False):
    user_home = os.path.expanduser("~")
    os.environ['TORCH_HOME'] = os.path.join(user_home, ".cache", "torch")
    os.environ['WHISPER_CACHE_DIR'] = os.path.join(user_home, ".cache", "whisper")
    os.environ['HF_HOME'] = os.path.join(user_home, ".cache", "huggingface")
    
    # Ensure directories exist
    for env_var in ['TORCH_HOME', 'WHISPER_CACHE_DIR', 'HF_HOME']:
        path = os.environ[env_var]
        os.makedirs(path, exist_ok=True)
'''
    
    # Write runtime hook file
    with open('runtime_hook.py', 'w') as f:
        f.write(runtime_hook_content)
    print("Created runtime_hook.py for model path configuration")
    
    spec_content = """
# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Collect Whisper data files dynamically
whisper_datas = collect_data_files('whisper')
# Also collect tiktoken data files (required for Whisper tokenization)
tiktoken_datas = collect_data_files('tiktoken')
tiktoken_cache_datas = collect_data_files('tiktoken_ext')

a = Analysis(
    ['captioner.py'],
    pathex=[],
    binaries=[],
    datas=whisper_datas + tiktoken_datas + tiktoken_cache_datas,
    hiddenimports=[
        'whisper',
        'openai', 
        'pyaudio',
        'numpy',
        'cryptography',
        'cryptography.fernet',
        'tkinter',
        'tkinter.ttk',
        'tkinter.font',
        'tkinter.messagebox',
        'threading',
        'queue',
        'json',
        'base64',
        'tempfile',
        'wave',
        'concurrent.futures',
        # Whisper dependencies - CRITICAL
        'torch',
        'torchaudio',
        'tiktoken',
        'numba',
        'librosa',
        'soundfile',
        'ffmpeg',
        # OpenAI dependencies - CRITICAL
        'httpx',
        'certifi',
        'distro',
        # Additional dependencies that might be missed
        'PIL',
        'regex',
        'tqdm',
        'more_itertools'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['runtime_hook.py'],
    excludes=[
        # Exclude unnecessary modules to reduce size
        'matplotlib',
        'scipy',
        'pandas',
        'jupyter',
        'notebook',
        'IPython'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='TWCC-Captioner',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Enable console for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico' if os.path.exists('icon.ico') else None,
    version='version_info.txt' if os.path.exists('version_info.txt') else None,
)
"""
    
    with open('captioner.spec', 'w') as f:
        f.write(spec_content)
    print("Created PyInstaller spec file!")

def build_executable():
    """Build the executable using PyInstaller."""
    print("Building standalone executable...")
    print("WARNING: This may take several minutes as it downloads and bundles dependencies...")
    
    # Clean previous builds
    if os.path.exists('dist'):
        shutil.rmtree('dist')
    if os.path.exists('build'):
        shutil.rmtree('build')
    
    # Build using the spec file
    subprocess.check_call([
        sys.executable, "-m", "PyInstaller", 
        "--clean",
        "captioner.spec"
    ])
    
    print("Executable built successfully!")
    print(f"Output location: {os.path.abspath('dist')}")

def create_version_info():
    """Create version info file for the executable."""
    version_info = """
# UTF-8
# Version Information for TWCC Captioner

VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(1, 0, 0, 0),
    prodvers=(1, 0, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'TWCC Development'),
        StringStruct(u'FileDescription', u'TWCC Universal Translator - Real-time Speech Translation'),
        StringStruct(u'FileVersion', u'1.0.0.0'),
        StringStruct(u'InternalName', u'TWCC-Captioner'),
        StringStruct(u'LegalCopyright', u'Copyright (C) 2024 Joshua Sommerfeldt'),
        StringStruct(u'OriginalFilename', u'TWCC-Captioner.exe'),
        StringStruct(u'ProductName', u'TWCC Universal Translator'),
        StringStruct(u'ProductVersion', u'1.0.0.0')])
      ]), 
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""
    
    with open('version_info.txt', 'w') as f:
        f.write(version_info)
    print("Created version info file!")

def create_readme():
    """Create a README for the executable distribution."""
    readme_content = """# TWCC Universal Translator - Standalone Executable

## What is this?
This is a standalone version of TWCC Universal Translator that provides real-time speech-to-text translation for live streaming and presentations.

## System Requirements
- Windows 10 or Windows 11
- Microphone access
- Internet connection (for translation services)
- OpenAI API key (you'll need to configure this in Settings)

## How to Use

### First Time Setup:
1. Run `TWCC-Captioner.exe`
2. Click "Settings" button
3. Enter your OpenAI API key (get one from https://platform.openai.com/api-keys)
4. Click "Save"

### Using the Application:
1. Select your target language from the dropdown
2. Adjust appearance settings (colors, font size) as needed
3. Click "Start Recording" to begin live translation
4. Speak into your microphone - translations will appear in real-time
5. Click "Stop Recording" when finished

### For Streaming:
- The window stays on top of other applications
- Customize colors and fonts to match your stream theme
- Use auto-clear settings to prevent subtitle buildup
- Position the window where you want subtitles to appear on stream

## Features
- 100+ language support
- Customizable appearance
- Cost tracking and session reports
- Secure API key storage
- Voice activity detection (ignores silence)

## Troubleshooting
- If no audio is detected, check your microphone permissions
- If translations don't appear, verify your OpenAI API key in Settings
- Session reports are saved to the 'expense_reports' folder

## Privacy & Security
- Your API key is encrypted and stored locally
- No audio data is stored permanently
- All processing happens on your computer and OpenAI's servers

---
For support or questions, visit: https://github.com/your-repo/TWCC-Captioner
"""
    
    with open('README_EXECUTABLE.txt', 'w') as f:
        f.write(readme_content)
    print("Created README for executable!")

def main():
    """Main build process."""
    print("TWCC Captioner - Executable Build Process")
    print("=" * 50)
    
    try:
        # Step 1: Install build dependencies
        install_build_dependencies()
        
        # Step 2: Create supporting files
        create_version_info()
        create_spec_file()
        create_readme()
        
        # Step 3: Build executable
        build_executable()
        
        # Step 4: Success message
        print("\n" + "=" * 50)
        print("BUILD SUCCESSFUL!")
        print("=" * 50)
        print(f"Your executable is located at: {os.path.abspath('dist/TWCC-Captioner.exe')}")
        print("\nNext steps:")
        print("1. Test the executable on your current machine")
        print("2. Copy the entire 'dist' folder to target computers")
        print("3. Run TWCC-Captioner.exe and configure API key in Settings")
        print("\nREMEMBER: Users will need their own OpenAI API key!")
        
        # Check if expense_reports directory should be included
        if os.path.exists('expense_reports'):
            print("\nTip: Copy your 'expense_reports' folder to dist/ if you want to include session reports")
        
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Build failed with error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 