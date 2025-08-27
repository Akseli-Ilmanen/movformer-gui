import av
import numpy as np
import dask.array as da
from dask import delayed
import threading
from pathlib import Path
from time import time, sleep


class VideoAudioReaderPlayer:
    """
    Production-ready segment player avoiding all common pitfalls
    """
    
    def __init__(self, video_path, audio_path=None):
        self.video_path = Path(video_path)
        self.audio_path = Path(audio_path) if audio_path else None
        
        # Initialize video
        self.video_container = av.open(str(self.video_path))
        self.video_stream = self.video_container.streams.video[0]
        self.video_fps = float(self.video_stream.average_rate)
        self.video_time_base = self.video_stream.time_base


        self._frame_playback_obj = None
        self._frame_is_playing = False
        # self.viewer.dims.events.current_step.connect(self.on_frame_change)

        # Initialize audio if provided
        if self.audio_path:
            self.audio_container = av.open(str(self.audio_path))
            self.audio_stream = self.audio_container.streams.audio[0]
            self.sample_rate = self.audio_stream.sample_rate
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Cache for performance
        self.frame_cache = {}
        self.cache_size = 100
        
   
        print(f"  Video: {self.video_stream.frames} frames @ {self.video_fps:.2f} fps")
        if self.audio_path:
            print(f"  Audio: {self.sample_rate} Hz")
    
    
    
    def extract_segment(self, start_seconds, end_seconds, chunk_size=30, include_audio=True):
        """
        Extract a segment using Dask for video and NumPy for audio.
        """
        duration_seconds = end_seconds - start_seconds
        video_dask = self.create_dask_array(start_seconds, duration_seconds, chunk_size)
        
        audio_data = None
        if include_audio and self.audio_path:
            audio_data = self._extract_audio_segment(start_seconds, end_seconds)
        return {
            'video_dask': video_dask,
            'audio_np': audio_data,
            'sr': self.sample_rate if audio_data is not None else None,
            'fps': self.video_fps,
        }
    
    
    def _extract_audio_segment(self, start_seconds, end_seconds):
        """Extract audio segment with sync"""
        target_timestamp = int(start_seconds * 1000000)
        self.audio_container.seek(target_timestamp)
        
        audio_chunks = []
        
        for frame in self.audio_container.decode(self.audio_stream):
            frame_time = frame.pts * self.audio_stream.time_base
            
            if frame_time < start_seconds:
                continue
            
            if frame_time >= end_seconds:
                break
            
            audio_chunks.append(frame.to_ndarray())
        
        return np.concatenate(audio_chunks) if audio_chunks else None


    def _extract_audio_segment(self, start_seconds, end_seconds):
        """Extract audio segment with sync"""
        target_timestamp = int(start_seconds * 1000000)
        self.audio_container.seek(target_timestamp)
        
        audio_chunks = []
        
        for frame in self.audio_container.decode(self.audio_stream):
            frame_time = frame.pts * self.audio_stream.time_base
            
            if frame_time < start_seconds:
                continue
            
            if frame_time >= end_seconds:
                break
            
            audio_chunks.append(frame.to_ndarray())
        
        return np.concatenate(audio_chunks) if audio_chunks else None
    


    def create_dask_array(self, start_seconds, duration_seconds, chunk_size=30):
        """
        Create a Dask array for the segment. Fast way to get video data.
        """
        start_frame = int(start_seconds * self.video_fps)
        total_frames = int(duration_seconds * self.video_fps)
        
        # Create delayed functions for each chunk
        @delayed
        def load_video_chunk(video_path, chunk_start, chunk_end, fps):
            """Load a chunk with proper resource management"""
            with av.open(str(video_path)) as container:
                stream = container.streams.video[0]
                
                target_time_seconds = chunk_start / fps
                timestamp_in_stream_base = target_time_seconds / stream.time_base
                
                container.seek(int(timestamp_in_stream_base))
                frames = []
                frame_idx = 0
                
                for frame in container.decode(stream):

                    
                    frame_time = frame.pts * stream.time_base
                    current_frame = int(frame_time * fps)
                    
            
                    if current_frame < chunk_start:
                        continue
                    
                    if current_frame >= chunk_end:
                        break
                    
                    frames.append(frame.to_ndarray(format='rgb24'))
                    frame_idx += 1
                
                # Pad if necessary
                expected_frames = chunk_end - chunk_start
                while len(frames) < expected_frames:
                    frames.append(np.zeros_like(frames[0]) if frames else 
                                np.zeros((stream.height, stream.width, 3), dtype=np.uint8))
                
                return np.array(frames[:expected_frames])
        
        # Build chunks
        chunks = []
        for i in range(0, total_frames, chunk_size):
            chunk_start = start_frame + i
            chunk_end = min(start_frame + i + chunk_size, start_frame + total_frames)
            
            chunk_data = load_video_chunk(
                self.video_path,
                chunk_start,
                chunk_end,
                self.video_fps
            )
            
            chunk_array = da.from_delayed(
                chunk_data,
                shape=(chunk_end - chunk_start, 
                      self.video_stream.height,
                      self.video_stream.width, 3),
                dtype=np.uint8
            )
            chunks.append(chunk_array)
        
        return da.concatenate(chunks, axis=0) if chunks else None




    def _extract_audio_segment(self, start_seconds, end_seconds):
        """Extract audio segment with sync"""
        target_timestamp = int(start_seconds * 1000000)
        self.audio_container.seek(target_timestamp)
        
        audio_chunks = []
        
        for frame in self.audio_container.decode(self.audio_stream):
            frame_time = frame.pts * self.audio_stream.time_base
            
            if frame_time < start_seconds:
                continue
            
            if frame_time >= end_seconds:
                break
            
            audio_chunks.append(frame.to_ndarray())
        
        return np.concatenate(audio_chunks) if audio_chunks else None
    
    
    
    
    
    
    
    
    def cleanup(self):
        """Proper resource cleanup"""
        with self.lock:
            if hasattr(self, 'video_container'):
                self.video_container.close()
            if hasattr(self, 'audio_container'):
                self.audio_container.close()
            self.frame_cache.clear()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    