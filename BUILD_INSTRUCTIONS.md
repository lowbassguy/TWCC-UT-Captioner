# Building TWCC Captioner as Windows Executable

This guide will help you create a standalone Windows executable (.exe) that can run on any Windows 10/11 computer without requiring Python installation.

## Prerequisites

1. **Python 3.8 or newer** installed on your development machine
2. **Internet connection** for downloading dependencies
3. **At least 4GB free disk space** (PyTorch and Whisper models are large)

## Quick Build Process

### Option 1: Using the Batch File (Easiest)
1. Double-click `build.bat`
2. Wait for the build process to complete (5-15 minutes)
3. Find your executable in the `dist` folder

### Option 2: Manual Build
1. Open Command Prompt or PowerShell in the project directory
2. Run: `python build_executable.py`
3. Wait for completion
4. Find your executable in the `dist` folder

## Detailed Step-by-Step Instructions

### Step 1: Prepare Your Environment
```cmd
# Install all required dependencies
pip install -r requirements.txt

# If you encounter any issues, try upgrading pip first:
python -m pip install --upgrade pip
```

### Step 2: Run the Build Script
```cmd
python build_executable.py
```

The script will:
- Install PyInstaller automatically
- Create configuration files
- Bundle all dependencies
- Generate a single executable file

### Step 3: Test the Executable
1. Navigate to the `dist` folder
2. Run `TWCC-Captioner.exe`
3. Configure your OpenAI API key in Settings
4. Test recording and translation functionality

## What Gets Created

After building, you'll have:
```
dist/
├── TWCC-Captioner.exe          # Main executable
├── README_EXECUTABLE.txt       # User instructions
└── [Various DLL and support files]
```

## Distribution

To distribute your application:

1. **Copy the entire `dist` folder** to target computers
2. Optionally rename the folder to something like "TWCC-Captioner-v1.0"
3. Users only need to run `TWCC-Captioner.exe`

### Creating a ZIP Distribution
```cmd
# After building, create a distributable ZIP
powershell Compress-Archive -Path dist -DestinationPath TWCC-Captioner-Windows.zip
```

## Troubleshooting

### Common Build Issues

#### "Module not found" errors
```cmd
# Solution: Install missing dependencies
pip install [missing-module-name]
```

#### Build takes too long or fails
```cmd
# Clear previous builds and try again
rmdir /s dist
rmdir /s build
python build_executable.py
```

#### PyAudio installation issues on Windows
```cmd
# Install Windows audio libraries
pip install pipwin
pipwin install pyaudio
```

#### Whisper model download issues
- Ensure stable internet connection
- The first run downloads ~1GB of AI models
- Subsequent builds reuse downloaded models

### Runtime Issues (for end users)

#### "MSVCR140.dll missing"
- Install Microsoft Visual C++ Redistributable 2015-2022
- Download from Microsoft's official website

#### Microphone not working
- Check Windows microphone permissions
- Try running as administrator

#### OpenAI API errors
- Verify API key is correctly entered in Settings
- Check internet connection
- Ensure OpenAI account has sufficient credits

## Technical Details

### File Size
- Expected executable size: 500MB - 1.5GB
- Large size due to:
  - PyTorch (~400MB)
  - Whisper models (~150MB)
  - Python runtime (~100MB)

### Performance
- First launch: 10-30 seconds (loading AI models)
- Subsequent launches: 5-15 seconds
- Real-time performance matches Python version

### Compatibility
- Works on Windows 10 (version 1903+)
- Works on Windows 11
- Requires ~2GB RAM during operation
- Benefits from dedicated GPU (optional)

## Advanced Configuration

### Custom Icon
1. Add `icon.ico` file to project directory
2. Rebuild executable
3. Icon will be automatically included

### Debug Mode
To enable console output for debugging:
1. Edit `captioner.spec`
2. Change `console=False` to `console=True`
3. Rebuild

### Reducing File Size
You can reduce executable size by:
1. Using CPU-only PyTorch (smaller but slower)
2. Excluding unused Whisper models
3. Customizing the PyInstaller spec file

## Security Notes

- The executable is not code-signed by default
- Windows may show security warnings
- Users may need to allow the app through Windows Defender
- For distribution, consider code signing for trust

## Support

If you encounter issues:
1. Check the console output for error messages
2. Verify all dependencies are installed
3. Try building on a clean Python environment
4. Check PyInstaller documentation for advanced options

---

**Build Time Expectations:**
- First build: 10-20 minutes (downloading models)
- Subsequent builds: 5-10 minutes
- Final executable: 500MB - 1.5GB 