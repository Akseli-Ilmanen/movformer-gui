"""PyQtGraph-based spectrogram plot combining best of both approaches."""

import pyqtgraph as pg
import numpy as np
from scipy.signal import spectrogram
from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QPen, QColor
from .audio_cache import SharedAudioCache
from .enhanced_time_axis import EnhancedTimeAxisItem

class SpectrogramPlot(pg.PlotWidget):
    """Spectrogram plot with integrated features from audian.
    
    Features:
    - Buffered spectrogram computation
    - Interactive colorbar
    - Power spectrum side panel
    - Filter handles for highpass/lowpass
    - Synchronized with line plots and labels
    """
    
    sigFilterChanged = Signal(float, float)  # highpass, lowpass
    
    def __init__(self, app_state, parent=None):
        super().__init__(parent)
        self.app_state = app_state
        
        # Configure plot
        self.setLabel('left', 'Frequency', units='Hz')
        self.setLabel('bottom', 'Time', units='s')
        self.showGrid(x=True, y=True, alpha=0.3)
        
        self.spec_item = pg.ImageItem()
        self.addItem(self.spec_item)
        
        self.init_colorbar()
        
        self.buffer = SpectrogramBuffer(app_state)
        
        self.current_range = None
        

        self.time_axis = EnhancedTimeAxisItem()
        self.setAxisItems({'bottom': self.time_axis})
        
    def init_colorbar(self):
        """Initialize interactive colorbar."""
        # Create gradient for colormap
        self.gradient = pg.GradientEditorItem()
        self.gradient.loadPreset('viridis')
        
        # Link to image
        self.gradient.setImageItem(self.spec_item)
        
        # Position gradient as colorbar
        self.gradient.setOrientation('right')
        self.gradient.sigGradientChanged.connect(self.update_colormap)
        
        # Set initial levels
        vmin = self.app_state.get_with_default("vmin_db")
        vmax = self.app_state.get_with_default("vmax_db")
        self.spec_item.setLevels([vmin, vmax])
        
            
    def update_spectrogram(self, t0=None, t1=None):
        """Update spectrogram for given time range."""
        if not hasattr(self.app_state, 'audio_path'):
            return
            
        # Get current view range if not specified
        if t0 is None or t1 is None:
            xmin, xmax = self.getViewBox().viewRange()[0]
            t0, t1 = xmin, xmax
            
        # Check if we need to recompute
        if self.buffer.needs_update(t0, t1, self.app_state.audio_path):
            # Compute spectrogram
            Sxx, freqs, times = self.buffer.compute(
                self.app_state.audio_path, t0, t1
            )
            
            if Sxx is not None:
                # Update image
                self.spec_item.setImage(Sxx.T, autoLevels=False)
                
                # Set transform to match time/frequency axes
                tr = pg.QtGui.QTransform()
                tr.translate(t0, freqs[0])
                tr.scale((t1-t0)/Sxx.shape[1], 
                        (freqs[-1]-freqs[0])/Sxx.shape[0])
                self.spec_item.setTransform(tr)
                
    
                    
        self.current_range = (t0, t1)
        
    def sync_with_lineplot(self, lineplot):
        """Synchronize x-axis with line plot."""
        self.setXLink(lineplot)
        
    def set_time_mode(self, mode):
        """Set time axis display mode."""
        self.time_axis.set_time_mode(mode)
        

class SpectrogramBuffer:
    """Smart buffering for spectrogram computation."""
    
    def __init__(self, app_state):
        self.app_state = app_state
        self.cache = {}
        self.current_path = None
        self.buffer_multiplier = app_state.get_with_default("spec_buffer")
        
    def needs_update(self, t0, t1, audio_path):
        """Check if buffer needs update."""
        if audio_path != self.current_path:
            self.cache.clear()
            self.current_path = audio_path
            return True
            
        # Check cache
        key = self._get_cache_key(t0, t1)
        return key not in self.cache
        
    def compute(self, audio_path, t0, t1):
        """Compute or retrieve spectrogram from cache."""
        key = self._get_cache_key(t0, t1)
        
        if key in self.cache:
            return self.cache[key]
            
        # Compute with buffer
        buffer_size = (t1 - t0) * self.buffer_multiplier
        buffer_t0 = max(0, t0 - buffer_size/2)
        buffer_t1 = t1 + buffer_size/2
        
        # Get audio data
        audio_loader = SharedAudioCache.get_loader(audio_path)
        if not audio_loader:
            return None, None, None
            
        fs = audio_loader.rate
        i0 = int(buffer_t0 * fs)
        i1 = int(buffer_t1 * fs)
        
        audio_data = audio_loader[i0:i1]
        if audio_data.ndim > 1:
            audio_data = np.mean(audio_data, axis=1)
            
        # Compute spectrogram
        nfft = self.app_state.get_with_default("nfft")
        hop = int(nfft * self.app_state.get_with_default("hop_frac"))
        
        freqs, times, Sxx = spectrogram(
            audio_data, fs=fs, 
            nperseg=nfft, noverlap=nfft-hop
        )
        
        # Convert to dB
        Sxx_db = 10 * np.log10(Sxx + 1e-10)
        
        # Adjust times to absolute
        times += buffer_t0
        
        # Cache result
        self.cache[key] = (Sxx_db, freqs, times)
        
        # Trim cache if too large
        if len(self.cache) > 10:
            # Remove oldest entries
            keys = sorted(self.cache.keys())
            for k in keys[:-10]:
                del self.cache[k]
                
        return Sxx_db, freqs, times
        
    def _get_cache_key(self, t0, t1):
        """Generate cache key for time range."""
        # Round to nearest 0.1s for caching
        return (round(t0, 1), round(t1, 1))