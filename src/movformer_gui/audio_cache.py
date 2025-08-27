"""Shared audio cache for efficient AudioLoader management."""

from audioio import AudioLoader
import threading


class SharedAudioCache:
    """Singleton cache for AudioLoader instances.
    
    This prevents repeatedly opening/closing audio files when computing
    spectrograms or accessing audio data from different parts of the application.
    Thread-safe implementation.
    """
    
    _instances = {}
    _lock = threading.Lock()
    
    @classmethod
    def get_loader(cls, audio_path, buffer_size=10.0):
        """Get or create AudioLoader for given audio path.
        
        Parameters
        ----------
        audio_path : str
            Path to audio file
        buffer_size : float
            Buffer size in seconds for AudioLoader
            
        Returns
        -------
        AudioLoader
            Cached or new AudioLoader instance
        """
        if not audio_path:
            return None
            
        with cls._lock:
            if audio_path not in cls._instances:
                try:
                    cls._instances[audio_path] = AudioLoader(audio_path, buffersize=buffer_size)
                except Exception as e:
                    print(f"Failed to load audio file {audio_path}: {e}")
                    return None
            return cls._instances[audio_path]
    
    @classmethod
    def clear_cache(cls):
        """Clear all cached AudioLoader instances."""
        with cls._lock:
            cls._instances.clear()
    
    @classmethod
    def remove_loader(cls, audio_path):
        """Remove specific AudioLoader from cache."""
        with cls._lock:
            if audio_path in cls._instances:
                del cls._instances[audio_path]