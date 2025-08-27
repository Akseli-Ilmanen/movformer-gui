import napari
import av
import numpy as np
from qtpy.QtCore import QTimer
from qtpy.QtWidgets import QApplication
import threading
import queue

class VideoStreamViewer:
    def __init__(self, source, viewer=None):
        """
        Initialize video stream viewer
        
        Parameters:
        - source: video file path or stream URL (e.g., rtsp://, http://, or webcam index)
        """
        self.source = source
        self.viewer = viewer or napari.Viewer()
        self.frame_queue = queue.Queue(maxsize=10)
        self.is_running = False
        
        # Initialize the video container
        self.container = None
        self.video_stream = None
        
        # Setup the image layer
        self.image_layer = None
        
        # Setup update timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        
    def start(self):
        """Start streaming video to napari"""
        # Open the video source
        self.container = av.open(self.source)
        self.video_stream = self.container.streams.video[0]
        
        # Get first frame to initialize the layer
        first_frame = self._get_frame()
        if first_frame is not None:
            self.image_layer = self.viewer.add_image(
                first_frame,
                name='Video Stream'
            )
        
        # Start the decoding thread
        self.is_running = True
        self.decode_thread = threading.Thread(target=self._decode_frames)
        self.decode_thread.daemon = True
        self.decode_thread.start()
        
        # Start the timer to update display
        self.timer.start(33)  # ~30 FPS
        
    def _decode_frames(self):
        """Decode frames in a separate thread"""
        try:
            for packet in self.container.demux(self.video_stream):
                if not self.is_running:
                    break
                    
                for frame in packet.decode():
                    # Convert frame to numpy array
                    img = frame.to_ndarray(format='rgb24')
                    
                    # Try to add to queue, skip if full
                    try:
                        self.frame_queue.put(img, block=False)
                    except queue.Full:
                        pass
        except Exception as e:
            print(f"Decoding error: {e}")
            
    def _get_frame(self):
        """Get a single frame from the video"""
        for packet in self.container.demux(self.video_stream):
            for frame in packet.decode():
                return frame.to_ndarray(format='rgb24')
        return None
        
    def update_frame(self):
        """Update the napari image layer with new frame"""
        try:
            if not self.frame_queue.empty():
                frame = self.frame_queue.get(block=False)
                if self.image_layer is not None:
                    self.image_layer.data = frame
        except queue.Empty:
            pass
            
    def stop(self):
        """Stop the video stream"""
        self.is_running = False
        self.timer.stop()
        if self.container:
            self.container.close()

# Usage example
if __name__ == "__main__":
    import napari
    
    # For a video file
    viewer = napari.Viewer()
    stream = VideoStreamViewer(r"C:\Users\Admin\Documents\Akseli\bird\bird_orig.mp4", viewer)
    stream.start()
    
    # For a webcam (on Linux/Mac)
    # stream = VideoStreamViewer('/dev/video0', viewer)
    
    # For an RTSP stream
    # stream = VideoStreamViewer('rtsp://example.com/stream', viewer)
    
    napari.run()