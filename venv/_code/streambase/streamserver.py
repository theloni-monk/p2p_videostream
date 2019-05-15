import socket
from .netutils import send_msg
import numpy as np
import io #BytesIO object replaces tempfile functionality
import zstandard as zstd
import numba as nb # jit optimization

#BIG TODO: optimize streaming code

@nb.njit(parallel = True, fastmath = True)
def diffReplace(img, diffMin): #TODO: FIXME client side
    img = img.ravel()        
    for idx in range(img.size):
        if img[idx] < diffMin:
            img[idx] = 0



class Server:
    """Server class for videostreamer, encodes frames and diffs them before sending"""

    def __init__(self, incoming_ip, **kwargs):
        """args: incoming_ip | kwargs: verbose/False, port/8080, elevateErrors/False"""
        self.verbose = kwargs.get("verbose", False)

        self.port = kwargs.get("port", 8080)
        self.incoming_ip = incoming_ip
        self.connected = False
        self.s = None
        self.conn = "hello"
        self.clientAddr = "clownFish"

        self.error=None
        self.elevateErrors = kwargs.get("elevateErrors", True)

        self._DIFFMIN=kwargs.get("_diffmin", 0)

        # the compressor cant be pickled for multiprocessing so it has to be initialized later
        self.cParams = None # zstd.ZstdCompressionParameters.from_level(5, threads=4)      
        self.C = None # zstd.ZstdCompressor(compression_params=cParams)
        self.isConnected = False
        self.log("Server ready")

    def log(self, m):
        """Prints out if verbose"""
        if self.verbose:
            print(m)  # printout if verbose

    def initializeSock(self, sock=None, **kwargs):
        self.log("streamserver initilizing socket")
        if not sock:
            s = socket.socket()
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((kwargs.get("bindto", ""), self.port))
            self.s = s
            self.s.listen(10)
        else:
            self.s = sock

    def serve(self, asy = False):
        """Blocks and waits for client at self.incoming_ip to connect"""
        if not self.s:
            self.initializeSock()
        self.log("streamserver Searching for client at {}...".format(self.incoming_ip))
        while True:
            # wait for client to query the server for a connection
            conn, clientAddr = self.s.accept()
            if clientAddr[0] == self.incoming_ip:
                self.conn = conn
                print(self.conn)
                self.clientAddr = clientAddr
                self.log('streamserver connected to ' +
                         self.clientAddr[0] + ':' + str(self.clientAddr[1]))
                
                if asy: return clientAddr, conn # HACK FOR ASYNC 
                return None  

            conn.close()
            self.log('Refused connection to ' +
                     clientAddr[0] + ':' + str(clientAddr[1]))

    def serveNoBlock(self, callback=None):
        """DEPRACATED Without blocking, waits for client at self.incoming_ip to connect, if callback given calls callback with arg True on success or False on failure
        Returns: False on failure, True on success"""

        self.log("Searching for client at {}...".format(self.incoming_ip))
        if not self.s:
            self.initializeSock()
        # wait for client to query the server for a connection
        self.s.setblocking(0)
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
        Tfile = io.BytesIO()
        self.cParams = zstd.ZstdCompressionParameters.from_level(5, threads=4)
        self.C = zstd.ZstdCompressor(compression_params=self.cParams)
        self.prevFrame = img
        np.save(Tfile, self.prevFrame)
        inF = self.C.compress(Tfile.getvalue())
        #inF = encodeDiff(img, self.C)

        send_msg(self.conn, inF)
        self.log("Sent {}KB (frame {})".format(
            int(len(inF)/1000), "initial"))
        self.frameno = 0
        self.isConnected=True

    def sendFrame(self, img, diffMin=0):
        """Sends single frame with intra-frame compression over an initialized stream"""
        #try:
        #    self.prevFrame
        #except AttributeError:
        #    self.initializeStream(img) #IM GETTING RID OF THE CHECK FOR OPTIMIZATION
        #PLZ BE SAFE

        # use numpys built in save function serialize the diff with prevframe
        # because we diff it it will compress more
        diff = img - self.prevFrame
        # saving prev frame
        self.prevFrame = img

        # for jittery cameras it might be worth it to only send only send signifigant changes to ease network strain
        if diffMin>0:
            diffReplace(img, diffMin) # detremental at higher resolution

        Tfile = io.BytesIO()
        np.save(Tfile, diff) # serialize frame from numpy array to bytes
        # return compressed bytes
        b = self.C.compress(Tfile.getvalue())
        

        # send it
        try:
            send_msg(self.conn, b)
        except Exception as e:
            self.log("failed to send message")
            self.close(e)

        self.log("Sent {}KB (frame {})".format(
            int(len(b)/1000), self.frameno))  # debugging
        self.frameno += 1

    def close(self, E=None, **kwargs):
        """Closes socket"""

        if(E != None):
            self.error=E
            
            if self.elevateErrors:
                self.log("Streamserver is raising Error: " + str(E)) 
                raise E
            self.log("Streamserver closed on Error: " + str(E)) 

        else:
            self.log("Streamserver closed")

        if self.s:
            self.s.close()

        if kwargs.get("destroy", False) == True:
            self.log("Deleting self")
            del self
