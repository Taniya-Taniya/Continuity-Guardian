"""
Frame extraction utility — pulls a single frame out of a video file
at a given timestamp and saves it as a PNG. Used to give the
dashboard something to actually SHOW (a real frame) instead of an
empty box, and to draw the Continuity Agent's flagged region on top
of a real image instead of just printing a sentence.

Uses OpenCV (bundles its own video decoding, no separate ffmpeg
install needed).
"""

from pathlib import Path

import cv2


def extract_frame(video_path: str, timestamp_sec: float, out_path: str) -> bool:
    """
    Saves the frame nearest to timestamp_sec from video_path to
    out_path (PNG). Returns True on success, False if the video
    couldn't be read or the timestamp is past the video's length —
    callers should treat False as "no thumbnail available," not fatal.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return False

    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    frame_number = max(0, int(timestamp_sec * fps))
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

    success, frame = cap.read()
    cap.release()

    if not success:
        return False

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(out_path, frame)
    return True
