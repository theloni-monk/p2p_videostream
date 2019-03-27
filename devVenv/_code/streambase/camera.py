import cv2
import numpy as np
from multiprocessing import Process, Pipe


class Camera():
    def __init__(self, **kwargs):
        self.mirror = kwargs.get("mirror", False)
        # captures from the first webcam it sees by default
        self.cap = cv2.VideoCapture(kwargs.get("device", 0))
        self.resolution = (self.cap.get(cv2.CAP_PROP_FRAME_WIDTH),
                           self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.output = None

    @property
    def frameNum(self):
        return self.cap.get(cv2.CAP_PROP_POS_FRAMES)

    @property
    def fps(self):
        # NOTE: unsure if this returns max fps of camera or current fps of camera
        return self.cap.get(cv2.CAP_PROP_FPS)

    @property
    def image(self):
        ret_val, img = self.cap.read()
        if self.mirror:
            img = cv2.flip(img, 1)
        self.output = img
        return img


if __name__ == "__main__":
    cam = Camera(mirror=True)
    print(cam.frameNum)
    print(cam.fps)
    print(cam.resolution)
    cv2.imwrite("test/test_image.png", cam.image)
