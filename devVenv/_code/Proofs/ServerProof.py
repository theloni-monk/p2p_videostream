from . import streamserver, camera
import cv2

cam = camera.Camera(mirror=True)

def retrieveImage(cam, imgResize):
    """Basic function for retrieving camera data, for getFrame"""
    img= cv2.resize(cam.image, (0, 0), fx=imgResize[0], fy=imgResize[1])    
    return img
    
def startStream(serv, getFrame, args=[]):
    serv.initializeStream(serv.fetchFrame(getFrame, args))
    while True:
        serv.sendFrame(serv.fetchFrame(getFrame, args))

resize_cof = (1,1)  
server = streamserver.Server(port=5000, verbose=True)
server.serve()
startStream(server, retrieveImage, [cam, resize_cof])
