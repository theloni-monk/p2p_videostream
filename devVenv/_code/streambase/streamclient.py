import socket
from .netutils import *
import cv2
import numpy as np
import zstandard 
import io
import atexit
import sys


class Client:
    def __init__(self, **kwargs):

        self.verbose = kwargs.get("verbose", False)
        
        #NOTE: soon to be irrelevent
        self.windowRes = (640, 480)
        self.windowTitle=kwargs.get("Title","Feed")
        self.prevFrame = None

        # creates socket
        self.log("Initializing socket...")
        self.ip = kwargs.get("serverIp", "localhost")
        self.s = socket.socket()
        self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # connects via socket to server at provided ip over the provided port
        self.log("Connecting...")
        # connect over port
        self.s.connect((self.ip, kwargs.get("port", 8080)))

        # instanciate a decompressor which we can use to decompress our frames
        self.D = zstandard.ZstdDecompressor()

        # when the user exits or the stream crashes it closes so there arn't orfaned processes
        atexit.register(self.close)

        self.frameno=None
        self.log("Ready")

    def log(self, m):
        """prints out if verbose"""
        if self.verbose:
            print(m)  # printout if server is in verbose mode

    def recv(self, size=1024):
        """Recieves a single frame
        args:
            size: how big a frame should be
                default: 1024
        returns:
            single data frame
        """
        data = bytearray()
        while 1:
            buffer = self.s.recv(1024)
            data += buffer
            if len(buffer) == 1024:
                pass
            else:
                return data

    def initializeStream(self):
        """Recvs initial frame and preps"""
        img = np.zeros((3, 3))  # make blank img
        # initial frame cant use intra-frame compression
        self.prevFrame = np.load(io.BytesIO(
            self.D.decompress(recv_msg(self.s))))
        self.frameno = 0
        self.log("stream initialized")

    def decodeFrame(self):
        """Decodes single frame of data from an initialized stream"""
        try:
            r = recv_msg(self.s)  # gets the frame difference
        except Exception as e:
            self.close(e)

        try:
            if len(r) == 0:
                pass
        except Exception as e:
            self.close(Exception("Server sent Null data"))
        

        # load decompressed image
                # np.load creates an array from the serialized data
        img = (np.load(io.BytesIO(self.D.decompress(r)))  # decompress the incoming frame difference
                + self.prevFrame).astype("uint8")  # add the difference to the previous frame and convert to uint8 for safety

        self.log("recieved {}KB (frame {})".format(int(len(r)/1000), self.frameno))  # debugging
        self.frameno+=1

        self.prevFrame = img  # save the frame

        return img

    #TODO: deprecate function:
    def startStream(self):
        """Decodes files from stream and displays them"""  
        self.initializeStream() #decode initial frame 
        cv2.namedWindow(self.windowTitle, cv2.WINDOW_NORMAL)

        while True:
            img=self.decodeFrame() #decode frame

            cv2.imshow(self.windowTitle, cv2.resize(img, (0, 0), fx=1, fy=1))

            if cv2.waitKey(1) == 27:
                break  # esc to quit

    def close(self, E=None):
        """Closes socket and opencv instances"""
        self.s.close()
        if(E!=None):
            print("Stream closed on Error\n" + str(E))
        else:
            self.log("Stream closed")

        #TODO: write new client window outside of opencv
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass
        sys.exit(0)
