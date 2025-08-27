"""Spectrogram computation and plotting for audio data with buffering support."""

import numpy as np
from scipy.signal import spectrogram
from matplotlib.patches import Rectangle
from .audio_cache import SharedAudioCache


class BufferedSpectrogram:
    """Buffered spectrogram that maintains a larger time window and only recomputes when needed.
    
    This class implements a smart buffering system that maintains a larger time window 
    (typically 5x the display window) and only recomputes when the view moves significantly 
    beyond the current buffer.
    """
    
    def __init__(self, app_state, nfft=None, hop_frac=None, 
                 vmin_db=None, vmax_db=None,
                 buffer_multiplier=None, recompute_threshold=None):
        
        # Use app_state for all defaults
        self.app_state = app_state
        
        nfft = app_state.get_with_default("nfft")
        hop_frac = app_state.get_with_default("hop_frac")
        vmin_db = app_state.get_with_default("vmin_db")
        vmax_db = app_state.get_with_default("vmax_db")
        buffer_multiplier = app_state.get_with_default("buffer_multiplier")
        recompute_threshold = app_state.get_with_default("recompute_threshold")

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
        
        # Track current audio source
        self.current_audio_path = None
        
    def needs_recompute(self, t0, t1):
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
        
    def compute_spectrogram(self, audio_path, t0, t1):
        """Compute spectrogram for the given time range using SharedAudioCache.
        
        Parameters
        ----------
        audio_path : str
            Path to audio file
        t0 : float
            Start time in seconds  
        t1 : float
            End time in seconds
        """
        if t1 <= t0 or not audio_path:
            return None, None
            
        # Get cached audio loader
        audio_loader = SharedAudioCache.get_loader(
            audio_path, 
            buffer_size=self.app_state.get_with_default("audio_buffer")
        )
        
        if audio_loader is None:
            return None, None
            
        fs = audio_loader.rate
        i0 = max(0, int(t0 * fs))
        i1 = min(audio_loader.frames, int(t1 * fs))
        
        if i1 - i0 < self.nfft:
            return None, None
            
        # Load audio data
        x = audio_loader[i0:i1]
        
        if x is None:
            raise ValueError(f"Audio data could not be loaded for time window: {t0} - {t1}")
            
        if x.ndim == 2:  # mixdown if stereo/multi
            x = np.mean(x, axis=1)
            
        # Compute spectrogram
        f, t, Sxx = spectrogram(x, fs=fs, nperseg=self.nfft, 
                               noverlap=self.nfft - self.hop)
        
        # Convert to dB
        Sxx_db = 10 * np.log10(Sxx + 1e-10)
        
        # Store in buffer
        self.buffer_data = Sxx_db
        self.buffer_t0 = t0
        self.buffer_t1 = t1
        self.buffer_extent = [t0, t1, f[0], f[-1]]
        
        return Sxx_db, self.buffer_extent
        
    def plot_on_axes(self, ax, audio_path, t0, t1, window_size=3.0, spec_buffer=5.0):
        """Plot spectrogram on given axes with buffering.
        
        Parameters
        ----------
        ax : matplotlib.axes.Axes
            Axes to plot on
        audio_path : str
            Path to audio file
        t0, t1 : float
            Display time range in seconds
        window_size : float
            Display window size in seconds
        spec_buffer : float
            Buffer multiplier for spectrogram computation
        """
        if not audio_path:
            return
            
        # Check if audio source changed
        if self.current_audio_path != audio_path:
            self.clear_buffer()
            self.current_audio_path = audio_path
            
        # Calculate buffer range (larger than display range)
        buffer_margin = (spec_buffer - 1) * window_size / 2
        buffer_t0 = max(0, t0 - buffer_margin)
        buffer_t1 = t1 + buffer_margin
        
        # Check if we need to recompute
        if self.needs_recompute(buffer_t0, buffer_t1):
            self.compute_spectrogram(audio_path, buffer_t0, buffer_t1)
            
        # Plot the visible portion
        if self.buffer_data is not None:
            # Calculate indices for visible portion
            t_buffer = np.linspace(self.buffer_t0, self.buffer_t1, 
                                  self.buffer_data.shape[1])
            i0 = np.searchsorted(t_buffer, t0)
            i1 = np.searchsorted(t_buffer, t1)
            
            # Plot only visible portion
            visible_data = self.buffer_data[:, i0:i1]
            extent = [t0, t1, self.buffer_extent[2], self.buffer_extent[3]]
            
            im = ax.imshow(visible_data, aspect='auto', origin='lower',
                          extent=extent, vmin=self.vmin_db, vmax=self.vmax_db,
                          cmap='viridis')
            
            ax.set_xlabel('Time (s)')
            ax.set_ylabel('Frequency (Hz)')
            ax.set_xlim(t0, t1)
            
    def clear_buffer(self):
        """Clear the spectrogram buffer."""
        self.buffer_data = None
        self.buffer_extent = None
        self.buffer_t0 = None
        self.buffer_t1 = None