"""Spectrogram computation and plotting for audio data with buffering support."""

import numpy as np
from scipy.signal import spectrogram
from matplotlib.patches import Rectangle
from audioio import AudioLoader

class BufferedSpectrogram:

    """Buffered spectrogram that maintains a larger time window and only recomputes when needed.
    
    This class implements a smart buffering system inspired by the BufferedArray class from audioio.
    It maintains a larger time window (typically 5x the display window) and only recomputes the
    spectrogram when the view moves significantly beyond the current buffer.
    
    The buffering system works as follows:
    1. When plotting, it calculates a buffer range that is `buffer_multiplier` times larger than
       the requested display range
    2. If the requested range is within the current buffer, it reuses the cached data
    3. If the requested range extends beyond the buffer by more than `recompute_threshold` 
       fraction of the buffer size, it recomputes the entire buffer
    4. The buffer is centered around the requested range to minimize recomputation
    
    This approach provides smooth navigation while maintaining good performance by avoiding
    unnecessary recomputation of spectrogram data.
    
    Parameters
    ----------
    nfft : int
        FFT size / window length.
    hop_frac : float
        Hop as fraction of nfft (noverlap = nfft - hop).
    vmin_db : float
        Minimum dB for display.
    vmax_db : float
        Maximum dB for display.
    buffer_multiplier : float
        Buffer size as multiple of display window size (default: 5.0).
        A value of 5.0 means the buffer will be 5x larger than the display window.
    recompute_threshold : float
        Fraction of buffer size that triggers recomputation (default: 0.5).
        When the requested range extends beyond the buffer by more than this fraction,
        the entire buffer is recomputed.
    """
    
    
    def __init__(self, app_state, nfft: int = None, hop_frac: float = None, 
                 vmin_db: float = None, vmax_db: float = None,
                 buffer_multiplier: float = None, recompute_threshold: float = None):
        
        # Use app_state for all defaults
        self.app_state = app_state
        
        nfft = nfft if nfft is not None else app_state.get_with_default("nfft")
        hop_frac = hop_frac if hop_frac is not None else app_state.get_with_default("hop_frac")
        vmin_db = vmin_db if vmin_db is not None else app_state.get_with_default("vmin_db")
        vmax_db = vmax_db if vmax_db is not None else app_state.get_with_default("vmax_db")
        buffer_multiplier = buffer_multiplier if buffer_multiplier is not None else app_state.get_with_default("buffer_multiplier")
        recompute_threshold = recompute_threshold if recompute_threshold is not None else app_state.get_with_default("recompute_threshold")

        if nfft < 8:
            raise ValueError("nfft must be >= 8")
        if not (0 < hop_frac <= 1.0):
            raise ValueError("hop_frac must be in (0, 1]")
        if buffer_multiplier <= 1.0:
            raise ValueError("buffer_multiplier must be > 1.0")
        if not (0 < recompute_threshold < 1.0):
            raise ValueError("recompute_threshold must be in (0, 1)")

        self.nfft = int(nfft)
        self.hop = max(1, int(round(hop_frac * nfft)))
        self.vmin_db = float(vmin_db)
        self.vmax_db = float(vmax_db)
        self.buffer_multiplier = float(buffer_multiplier)
        self.recompute_threshold = float(recompute_threshold)

        # Buffer state
        self.buffer_t0 = None  # Start time of current buffer
        self.buffer_t1 = None  # End time of current buffer
        self.buffer_data = None  # Cached spectrogram data
        self.buffer_extent = None  # Cached extent information
     
     
    
    def load_audio_file(self, file_path: str, buffer_size: float = None):
        """
        Load audio file and return AudioLoader instance.
        Parameters
        ----------
        file_path : str
            Path to audio file
        buffer_size : float, optional
            Buffer size in seconds
        Returns
        -------
        AudioLoader
        """
        if buffer_size is None:
            buffer_size = self.app_state.get_with_default("audio_buffer")
        loader = AudioLoader(file_path, buffersize=buffer_size)
        return loader


        
    def needs_recompute(self, t0: float, t1: float) -> bool:
        """Check if spectrogram needs to be recomputed for the given time range."""
        if self.buffer_data is None:
            return True
            
        # Check if requested range is within buffer
        if t0 >= self.buffer_t0 and t1 <= self.buffer_t1:
            return False
            
        # Check if we need to recompute based on threshold
        buffer_size = self.buffer_t1 - self.buffer_t0
        threshold = buffer_size * self.recompute_threshold
        
        # If requested range extends beyond buffer by more than threshold, recompute
        if (t0 < self.buffer_t0 - threshold or 
            t1 > self.buffer_t1 + threshold):
            return True
            
        return False
        
    def compute_spectrogram(self, audio_loader, t0: float, t1: float):
        """Compute spectrogram for the given time range.
        
        Parameters
        ----------
        audio_loader : AudioLoader
            Audio data loader
        t0 : float
            Start time in seconds  
        t1 : float
            End time in seconds
        shared_cache : SharedAudioCache, optional
            Shared audio cache for efficient loading
        """
        if t1 <= t0 or audio_loader is None:
            return None, None
            
        fs = audio_loader.rate
        i0 = max(0, int(t0 * fs))
        i1 = min(audio_loader.frames, int(t1 * fs))
        
        if i1 - i0 < self.nfft:
            return None, None
            
        # Load audio data for the time window - use shared cache if available
        if shared_cache is not None:
            x = shared_cache.get_audio_segment(audio_loader, t0, t1)
        else:
            # Fallback to direct loading
            x = audio_loader[i0:i1]

        if x is None:
            raise ValueError(f"Audio data could not be loaded for the specified time window: {t0} - {t1}")
            
        if x.ndim == 2:  # mixdown if stereo/multi
            x = np.mean(x, axis=1)
        

        f, t, Sxx = spectrogram(x, fs=fs, nperseg=self.nfft, noverlap=self.nfft // 2)


