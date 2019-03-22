from streambase import camera,streamserver
import cv2

cam = camera.Camera(mirror=True)

def retrieveImage(cam, imgResize):
    """Basic function for retrieving camera data, for getFrame"""
    img= cv2.resize(cam.image, (0, 0), fx=imgResize[0], fy=imgResize[1])    
    return img
resize_cof = (1,1)  
server = streamserver.Server(port=5000, verbose=True)
server.serve()
server.startStream(retrieveImage, [cam, resize_cof])
