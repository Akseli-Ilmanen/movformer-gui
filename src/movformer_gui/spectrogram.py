"""Spectrogram computation and plotting for audio data with buffering support."""

import numpy as np
from scipy.signal import spectrogram
from matplotlib.patches import Rectangle


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
    
    def __init__(self, nfft: int = 1024, hop_frac: float = 0.5, 
                 vmin_db: float = -120.0, vmax_db: float = 20.0,
                 buffer_multiplier: float = 5.0, recompute_threshold: float = 0.5):
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
        """Compute spectrogram for the given time range."""
        if t1 <= t0 or audio_loader is None:
            return None, None
            
        fs = audio_loader.rate
        i0 = max(0, int(t0 * fs))
        i1 = min(audio_loader.frames, int(t1 * fs))
        
        if i1 - i0 < self.nfft:
            return None, None
            
        # Load audio data for the time window
        x = audio_loader[i0:i1]
        if x.ndim == 2:  # mixdown if stereo/multi
            x = np.mean(x, axis=1)
        
        # Compute spectrogram
        f, t, Sxx = spectrogram(
            x,
            fs=fs,
            nperseg=self.nfft,
            noverlap=self.nfft - self.hop,
            detrend=False,
            scaling="density",
            mode="psd",
        )
        
        # Convert to dB safely
        Sxx = 10.0 * np.log10(np.maximum(Sxx, np.finfo(float).tiny))
        
        # Calculate extent for proper time alignment
        extent = (t0, t0 + t[-1] if len(t) > 0 else t0, 
                 f[0] if len(f) > 0 else 0, 
                 f[-1] if len(f) > 0 else fs / 2.0)
        
        return Sxx, extent
        
    def plot_on_axes(self, ax, audio_loader, t0: float, t1: float, 
                     window_size: float = None, spec_buffer: float = None):
        """Compute spectrogram of audio in [t0, t1] and draw on given Matplotlib Axes.
        
        This method implements the core buffering logic:
        
        1. **Buffer Calculation**: 
           - If `window_size` is provided, the buffer is calculated as `window_size * buffer_multiplier`
           - The buffer is centered around the requested range [t0, t1]
           - If no `window_size` is provided, the buffer is calculated from the requested range
        
        2. **Smart Reuse**:
           - If the requested range [t0, t1] is within the current buffer, cached data is reused
           - This provides instant response for small navigation movements
        
        3. **Threshold-based Recomputation**:
           - Only recomputes when the requested range extends beyond the buffer by more than
             `recompute_threshold` fraction of the buffer size
           - This prevents unnecessary recomputation for small movements while ensuring
             smooth performance for large jumps
        
        Parameters
        ----------
        ax : matplotlib.axes.Axes
            The axes to plot on.
        audio_loader : AudioLoader
            Audio data loader.
        t0 : float
            Start time for display.
        t1 : float
            End time for display.
        window_size : float, optional
            Display window size in seconds. Used as reference for buffer calculation.
            If provided, the buffer will be `window_size * buffer_multiplier` seconds wide.
        spec_buffer : float, optional
            Buffer multiplier for spectrogram computation. Overrides the default
            `buffer_multiplier` set in the constructor.
            
        Returns
        -------
        matplotlib.image.AxesImage or None
            The image object for potential colorbar integration, or None if plotting failed.
            
        Notes
        -----
        The buffer calculation ensures that:
        - Forward jumps of up to 2.5x window_size can reuse the buffer
        - Backward jumps of up to 2.5x window_size can reuse the buffer
        - Only when jumping beyond these thresholds is recomputation triggered
        - This provides a natural feel for navigation while maintaining performance
        """
        if t1 <= t0 or audio_loader is None:
            return None
            
        # Use provided buffer multiplier or default
        buffer_mult = spec_buffer if spec_buffer is not None else self.buffer_multiplier
        
        # Calculate buffer range
        if window_size is not None and window_size > 0:
            # Use window_size as reference for buffer calculation
            buffer_size = window_size * buffer_mult
            buffer_t0 = t0 - (buffer_size - (t1 - t0)) / 2
            buffer_t1 = t0 + buffer_size
        else:
            # Use requested range as reference
            range_size = t1 - t0
            buffer_size = range_size * buffer_mult
            buffer_t0 = t0 - (buffer_size - range_size) / 2
            buffer_t1 = t0 + buffer_size
            
        # Clamp buffer to audio bounds
        fs = audio_loader.rate
        max_time = audio_loader.frames / fs
        buffer_t0 = max(0.0, buffer_t0)
        buffer_t1 = min(max_time, buffer_t1)
        
        # Check if we need to recompute
        if self.needs_recompute(buffer_t0, buffer_t1):
            # Compute new buffer
            Sxx, extent = self.compute_spectrogram(audio_loader, buffer_t0, buffer_t1)
            if Sxx is not None:
                self.buffer_data = Sxx
                self.buffer_extent = extent
                self.buffer_t0 = buffer_t0
                self.buffer_t1 = buffer_t1
            else:
                return None
        else:
            # Use cached data
            Sxx = self.buffer_data
            extent = self.buffer_extent
            
        if Sxx is None:
            return None
            
        # Plot spectrogram
        im = ax.imshow(
            Sxx,
            origin="lower",
            aspect="auto",
            extent=extent,
            vmin=self.vmin_db,
            vmax=self.vmax_db,
            cmap="magma",
        )
        
        # Set labels
        ax.set_ylabel("Frequency (Hz)")
        ax.set_xlabel("Time (s)")
        
        return im



# Currently not used
class Spectrogram:
    """Simple spectrogram helper that computes and plots an STFT over a time window.
    
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
    """
    
    def __init__(self, nfft: int = 1024, hop_frac: float = 0.5, 
                 vmin_db: float = -120.0, vmax_db: float = 20.0):
        if nfft < 8:
            raise ValueError("nfft must be >= 8")
        if not (0 < hop_frac <= 1.0):
            raise ValueError("hop_frac must be in (0, 1]")
        
        self.nfft = int(nfft)
        self.hop = max(1, int(round(hop_frac * nfft)))
        self.vmin_db = float(vmin_db)
        self.vmax_db = float(vmax_db)
    
    def plot_on_axes(self, ax, audio_loader, t0: float, t1: float):
        """Compute spectrogram of audio in [t0, t1] and draw on given Matplotlib Axes.
        
        Returns the image object for potential colorbar integration.
        """
        if t1 <= t0 or audio_loader is None:
            return None
            
        fs = audio_loader.rate
        i0 = max(0, int(t0 * fs))
        i1 = min(audio_loader.frames, int(t1 * fs))
        
        if i1 - i0 < self.nfft:
            return None
            
        # Load audio data for the time window
        x = audio_loader[i0:i1]
        if x.ndim == 2:  # mixdown if stereo/multi
            x = np.mean(x, axis=1)
        
        # Compute spectrogram
        f, t, Sxx = spectrogram(
            x,
            fs=fs,
            nperseg=self.nfft,
            noverlap=self.nfft - self.hop,
            detrend=False,
            scaling="density",
            mode="psd",
        )
        
        # Convert to dB safely
        Sxx = 10.0 * np.log10(np.maximum(Sxx, np.finfo(float).tiny))
        
        # Calculate extent for proper time alignment
        extent = (t0, t0 + t[-1] if len(t) > 0 else t0, 
                 f[0] if len(f) > 0 else 0, 
                 f[-1] if len(f) > 0 else fs / 2.0)
        
        # Plot spectrogram
        im = ax.imshow(
            Sxx,
            origin="lower",
            aspect="auto",
            extent=extent,
            vmin=self.vmin_db,
            vmax=self.vmax_db,
            cmap="magma",
        )
        
        # Set labels
        ax.set_ylabel("Frequency (Hz)")
        ax.set_xlabel("Time (s)")
        
        return im
