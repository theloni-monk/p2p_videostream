import socket
from .netutils import *
import cv2
import numpy as np
import io
from tempfile import TemporaryFile
import zstandard
import sys
import atexit


class Server:
    
    def __init__(self, incoming_ip, **kwargs):
        self.verbose = kwargs.get("verbose", False)

        self.port= kwargs.get("port", 8080)
        self.incoming_ip = incoming_ip
        self.connected = False

        atexit.register(self.close)
        
        self.log("Server ready")

    def log(self, m):
        """Prints out if verbose"""
        if self.verbose:
            print(m)  # printout if verbose

    def initializeSock(self,sock=None):
        self.log("Initilizing socket")
        if not sock:
            s = socket.socket()
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((kwargs.get("bindto", ""), port))
            self.s = s
            self.s.listen(10)
        else:
            self.s = sock

    def serve(self):
        """Blocks and waits for client at self.incoming_ip to connect"""
        self.log("Searching for client at {}...".format(self.incoming_ip))
        while True:
            # wait for client to query the server for a connection
            conn, clientAddr = self.s.accept()
            if clientAddr[0] == self.incoming_ip:
                self.conn = conn
                self.clientAddr = clientAddr
                self.log('Connected to ' +
                        self.clientAddr[0] + ':' + str(self.clientAddr[1]))
                return None  # only connects to one client
            conn.close()
            self.log('Refused connection to ' +
                        clientAddr[0] + ':' + str(clientAddr[1]))

    def serveNoBlock(self, callback=None):
        """Without blocking, waits for client at self.incoming_ip to connect, if callback given calls callback with arg True on success or False on failure
        Returns: False on failure, True on success"""
        
        self.log("Searching for client at {}...".format(self.incoming_ip))

        # wait for client to query the server for a connection
        conn, clientAddr = self.s.accept()
        if clientAddr[0] == self.incoming_ip:
            self.conn = conn
            self.clientAddr = clientAddr
            self.log('Connected to ' +
                self.clientAddr[0] + ':' + str(self.clientAddr[1]))
            if callback:
                callback(True)
            return True  # only connects to one client
        conn.close()
        self.log("serveNoBlock Failed!")
        self.log('Refused connection to ' +
                clientAddr[0] + ':' + str(clientAddr[1]))
        if callback:
            callback(False)
        return False

    def initializeStream(self, img):
        """Sends initial frame of compression and initializes compressor and io"""
        self.Sfile = io.BytesIO()
        self.C = zstandard.ZstdCompressor()
        self.prevFrame = img
        np.save(self.Sfile, self.prevFrame)
        send_msg(self.conn, self.C.compress(self.Sfile.getvalue()))
        self.frameno = 0

    def fetchFrame(self, getFrame, args=[]):
        """Fetches a frame given a function"""
        return getFrame(*args)

    def sendFrame(self, img):
        """Sends single frame with intra-frame compression over an initialized stream"""
        try:
            self.prevFrame
        except AttributeError:
            self.initializeStream()
        
        # instanciate temporary bytearray to send later
        Tfile = io.BytesIO()

        # use numpys built in save function to diff with prevframe
        # because we diff it it will compress more
        np.save(Tfile, img-self.prevFrame)

        # compress it into even less bytes
        b = self.C.compress(Tfile.getvalue())

        # saving prev frame
        self.prevFrame = img

        # send it
        try:
            send_msg(self.conn, b)
        except Exception as e:
            self.close(e)
        self.log("Sent {}KB (frame {})".format(int(len(b)/1000), self.frameno))  # debugging
        self.frameno += 1


    def close(self, E=None):
        """Closes socket"""
        self.s.close()
        if(E!=None):
            print("Stream closed on Error\n" + str(E))
        else:
            self.log("Stream closed")
        sys.exit(0)
