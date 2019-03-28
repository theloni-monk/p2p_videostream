from ..streambase import streamserver, camera
import cv2

cam = camera.Camera(mirror=True)


def retrieveImage(cam, imgResize):
    """Basic function for retrieving camera data, for getFrame"""
    img = cv2.resize(cam.image, (0, 0), fx=imgResize[0], fy=imgResize[1])
    return img


def startStream(serv, getFrame, args=[]):
    serv.initializeStream(getFrame(args[0],args[1]))
    while True:
        try:
                serv.sendFrame(getFrame(args[0],args[1]))
        except Exception:
                serv.close(destroy=True)
                break


resize_cof = (1, 1)
server = streamserver.Server("127.0.0.1", port=5000, verbose=True, elevateErrors=True)
server.serve()
startStream(server, retrieveImage, [cam, resize_cof])
