# Open video file with napari-pyav plugin
video_path = r"C:/Users/Admin/Documents/Akseli/bird_video_audio/bird.mp4"


from movformer_gui._reader import FastVideoReader
import napari

reader = FastVideoReader(video_path)

stack_frames = reader[20:41]  # frames 20 to 40 inclusive
viewer = napari.Viewer()
viewer.add_image(stack_frames, name="Frames 20-40", rgb=True)
napari.run()