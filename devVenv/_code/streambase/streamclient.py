import socket
from .netutils import *
import cv2
import numpy as np
import zstandard 
import io
import atexit
import sys


class Client:
    
    def __init__(self, target_ip, **kwargs):

        self.verbose = kwargs.get("verbose", False)
        
        self.target_ip = target_ip
        self.target_port = kwargs.get("port", 8080)

        self.connected = False
        
        # instanciate a decompressor which we can use to decompress our frames
        self.D = zstandard.ZstdDecompressor()

        # when the user exits or the stream crashes it closes so there arn't orfaned processes
        atexit.register(self.close)

        self.prevFrame = None
        self.frameno=None
        self.log("Client Ready")

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
    
    def initializeSock(sock=None):
        """Setter for self.s socket or makes blank socket"""
        if not sock:
            # creates socket
            self.log("Initializing socket...")
            self.s = socket.socket()
            self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((kwargs.get("bindto", ""), port))
        else:
            self.s=sock

    def connectSock():
        """ Connects socket to self.target_ip over self.port
            returns: True on connection, False on failed connection """
        #TODO: make encryption handshake
        self.log("Connecting...")
        try:
            self.s.connect((self.target_ip, self.port))
            self.connected=True
        except ConnectionRefusedError:
            self.log("connection refused") 
            self.connected=False
            return False
        return True
 
    def initializeStream(self):
        """Initializes and connects socket if uninitalized and receives initial frame"""

        if not self.s:
            self.initializeSock() # if socket wasn't created make it now
        if not self.connected:
            self.connectSock() # if socket wasn't connected connect now

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
