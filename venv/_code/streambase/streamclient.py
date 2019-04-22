import socket
from .netutils import recv_msg
import cv2
import numpy as np
import zstandard
import io
import atexit


class Client:
    """Client class for videostreamer, decodes compressed and diffed images"""

    def __init__(self, target_ip, **kwargs):
        """args: target_ip | kwargs: verbose/False, port/8080, elevateErrors/False"""
        self.verbose = kwargs.get("verbose", False)

        self.target_ip = target_ip
        self.port = kwargs.get("port", 8080)
        self.s = None
        self.connected = False

        # instanciate a decompressor which we can use to decompress our frames
        self.D = zstandard.ZstdDecompressor()

        # when the user exits or the stream crashes it closes so there arn't orfaned processes
        atexit.register(self.close)
        self.error=None
        self.elevateErrors = kwargs.get("elevateErrors", False)

        self.prevFrame = None
        self.frameno = None
        self.log("Client Ready")

    def log(self, m):
        """prints if self.verbose"""
        if self.verbose:
            print(m)  # printout if server is in verbose mode

    def recv(self, size=1024):
        # NOTE: this just works
        """Recieves a single frame
        args:
            size: how big a frame should be
                default: 1024 
        returns:
            single data frame
        """
        data = bytearray()
        while 1:
            buffer = self.s.recv(size)
            data += buffer
            if len(buffer) == size:
                pass
            else:
                return data

    def initializeSock(self, sock=None):
        """Setter for self.s socket or makes blank socket"""
        if not sock:
            # creates socket
            self.log("Initializing socket...")
            self.s = socket.socket()
            self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            #self.s.bind((kwargs.get("bindto", ""), self.port))
        else:
            self.s = sock

    def connectSock(self):
        """ Connects socket to self.target_ip over self.port
            returns: True on connection, False on failed connection """
        # TODO: make encryption handshake
        self.log("Connecting...")
        try:
            self.s.connect((self.target_ip, self.port))
            self.connected = True
        except ConnectionRefusedError:
            self.log("connection refused")
            self.connected = False
            return False
        return True

    def initializeStream(self):
        """Initializes and connects socket if uninitalized and receives initial frame"""

        if not self.s:
            self.initializeSock()  # if socket wasn't created make it now
        if not self.connected:
            self.connectSock()  # if socket wasn't connected connect now

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

        self.log("recieved {}KB (frame {})".format(
            int(len(r)/1000), self.frameno))  # debugging
        self.frameno += 1

        self.prevFrame = img  # save the frame

        return img

    def close(self, E=None, **kwargs):
        """Closes socket and opencv instances"""
        if self.s:
            self.s.close()

        if(E != None):
            self.error=E
            print("Streamclient closed on Error\n" + str(E))
            if self.elevateErrors:
                raise E
        else:
            self.log("Streamclient closed")
        
        if kwargs.get("destroy", False) == True:
            self.log("Destroying self")
            del self

