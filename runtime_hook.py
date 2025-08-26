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