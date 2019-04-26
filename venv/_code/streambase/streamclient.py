import socket
from .netutils import recv_msg
import cv2
import numpy as np
import zstandard as zstd
import io
import numba as nb


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
        self.D = zstd.ZstdDecompressor()

        self.error=None
        self.elevateErrors = kwargs.get("elevateErrors", True)

        self.prevFrame = None
        self.frameno = None
        self.isConnected = False
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
            self.log("streamclient initializing socket...")
            self.s = socket.socket()
            self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            #self.s.bind((kwargs.get("bindto", ""), self.port))
        else:
            self.s = sock

    def connectSock(self):
        """ Connects socket to self.target_ip over self.port
            returns: True on connection, False on failed connection """
        # TODO: make encryption handshake
        self.log("streamclient connecting to server...")
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
        self.isConnected=True

    def decodeFrame(self):
        """Decodes single frame of data from an initialized stream"""
        try:
            r = recv_msg(self.s)  # gets the frame difference
        except Exception as e:
            self.close(e)
            return None

        try:
            if len(r) == 0:
                pass
        except Exception as e:
            self.close(Exception("Server sent Null data"))
            return None

        # load decompressed image
        img = (np.load(io.BytesIO(self.D.decompress(r)))  # decompress the incoming frame difference
                + self.prevFrame).astype("uint8")  # add the difference to the previous frame and convert to uint8 for safety


        self.log("recieved {}KB (frame {})".format(
            int(len(r)/1000), self.frameno))  # debugging
        self.frameno += 1

        self.prevFrame = img  # save the frame

        return img

    def close(self, E=None, **kwargs):
        """Closes socket and opencv instances"""

        if(E != None):
            self.error=E
            if self.elevateErrors:
                print("Streamclient is raising Error: " + str(E))
                raise E
            print("Streamclient closed on Error: " + str(E))
        else:
            self.log("Streamclient closed")
        
        if self.s:
            self.s.close()

        if kwargs.get("destroy", False) == True:
            self.log("Destroying self")
            del self

