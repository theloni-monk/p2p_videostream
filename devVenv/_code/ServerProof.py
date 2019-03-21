from streambase import camera,streamserver

cam = camera.Camera(mirror=True)

def retrieveImage(cam, imgResize):
    """Basic function for retrieving camera data, for getFrame"""
    cv2.resize(cam.image, (0, 0), fx=imgResize[0], fy=imgResize[1])
    
    return image
resize_cof = (1,1)  
server = streamserver.Server(port=5000, verbose=True)
server.serve()
server.startStream(retrieveImage, [cam, resize_cof])

#for i in range(10):
#    cv2.imwrite("test_image.png", cam.image)