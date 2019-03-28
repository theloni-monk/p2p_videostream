#from .streambase.streamserver import *
#from .streambase.streamclient import *
#from .streambase.camera import Camera
#from .streambase.netutils import *
from .streambase import *
import socket
import random
import time
import pickle
# for getting public ip:
from json import load
from urllib.request import urlopen
# for accessing stream data
import threading
from queue import Queue

# HACK: this makes the urllib requrest work
import ssl
ssl._create_default_https_context = ssl._create_unverified_context


class ServerThread(threading.Thread):
    """Thread that offloads initialization, encoding, and sending frames"""

    def __init__(self, vidserver, frameFunc, frameFuncArgs=[]):
        threading.Thread.__init__(self)
        self.server = vidserver
        self.getFrame = frameFunc
        self.getFrameArgs = frameFuncArgs

    def run(self):
        Er = None
        self.server.initializeStream(self.getFrame(self.getFrameArgs))
        while True:
            try:
                self.server.sendFrame(self.getFrame(self.getFrameArgs))
            except Exception as e:
                Er = e
                break
        raise Er


class ClientThread(threading.Thread):
    """Thread that offloads initialization, receiving, and decoding frames and puts them in given Queue"""

    def __init__(self, vidclient, fQueue):
        threading.Thread.__init__(self)
        self.client = vidclient
        self.fQueue = fQueue

    def run(self):
        Er = None
        self.client.initializeStream()
        while True:
            try:
                self.fQueue.put(self.client.decodeFrame())
            except Exception as e:
                Er = e
                break
        raise Er


class VidStreamerData():
    """Wrapper for name, ip, cameraResolution, and orientation"""

    def __init__(self):
        self.name = None
        self.ip = None
        self.cameraResolution = None
        self.orientation = None  # usesless for now


class VidStreamer:
    """VidStreamer is a wrapper for a client and a server with a control socket to connect to other vistreamers"""

    def __init__(self, partner_ip, **kwargs):

        self.verbose = kwargs.get("verbose", False)
        self.name = kwargs.get("name", "VidBot")
        self.cam = camera.Camera()

        # datastruct setup
        self.data = VidStreamerData()
        self.data.name = self.name
        try:
            self.data.ip = load(
                urlopen('https://api.ipify.org/?format=json'))['ip']
        except Exception as e:
            print(str(e))
            raise Exception("No Internet connection available!")

        self.data.cameraResolution = self.cam.resolution
        self.data.orientation = True  # always horizontal for now

        self.pData = None

        self.partner_ip = partner_ip
        self.comm_port = kwargs.get("port", 8080)

        self.CliBase = streamclient.Client(
            partner_ip, port=self.comm_port, verbose=self.verbose)
        self.SerBase = streamserver.Server(
            partner_ip, port=self.comm_port, verbose=self.verbose)

        self.controlSockConnector = socket.socket(socket.AF_INET)
        self.controlSockConnector.setsockopt(
            socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.connected = False
        self.controlSock = None

        self.isPaused = False

        self.frameQueue = Queue()
        self.serverThread = None
        self.clientThread = None

    def log(self, m):
        """prints if self.verbose"""
        if self.verbose:
            print(m)

    def connectPartner(self, timeout=None):
        """blocking, randomly switches between listening and attempting to connect to self.partner_ip with a correct name
        Returns: False on timeout, True on connection"""
        stime = time.time()
        while True:
            connected = False
            # Attempt to serve for a random amount of time:
            self.controlSockConnector.listen(10)
            self.controlSockConnector.settimeout(random.randint(5, 15))
            conn = None
            try:
                conn, clientAddr = self.controlSockConnector.accept()
            except Exception as e:
                self.log(e)
            if conn:  # if it didn't get accepted just move on
                if clientAddr[0] == self.partner_ip:
                    self.controlSock = conn
                    self.clientAddr = clientAddr
                    self.log('ControlSock, connected to ' +
                             self.clientAddr[0] + ':' + str(self.clientAddr[1]))
                    self.connected = True
                    return True  # only connects to one client
                # else:
                conn.close()
                self.log('Refused connection to ' +
                         clientAddr[0] + ':' + str(clientAddr[1]))

            # Attempt to connect a random number of times:
            for i in range(random.randint(5, 10)):
                try:
                    self.controlSockConnector.connect((self.partner_ip, self.comm_port))
                    connected = True
                except ConnectionRefusedError:
                    connected = False

                if connected:
                    self.controlSock = self.controlSockConnector
                    self.connected = True
                    return True

            # Check for timeout:
            if timeout:
                if time.time() > stime + timeout:
                    return False

    def cSockRecv(self, size=1024):
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
            buffer = self.controlSock.recv(size)
            data += buffer
            if len(buffer) == size:
                pass
            else:
                return data

    def init_infoExchange(self):
        """initial info exchange over controlsocket about things like name, resolution, and orientation via VidStreamerData struct"""
        # send self.data
        try:
            netutils.send_msg(self.controlSock, pickle.dump(self.data))
        except Exception as e:
            self.close(e)
        self.log("Sent self.data")

        try:
            self.pData = pickle.load(self.cSockRecv())
        except Exception as e:
            self.close(e)
        self.log("Recieved self.pData")

        # check if data is null:
        try:
            if len(self.pData) == 0:
                pass
        except Exception as e:
            self.close(Exception("Partner sent Null data for self.pData"))

    def initComps(self, **kwargs):
        """ initializes the server and client of the vidstreamer and connects them """

        if not self.connected:
            self.connectPartner(kwargs.get("timeout", None))

        self.SerBase.initializeSock()
        self.SerBase.serveNoBlock()

        self.CliBase.initializeSock()
        self.CliBase.connectSock()

    def defaultCamFunc(self):
        """Funcional wrapper for self.cam.image @property"""
        return self.cam.image

    def beginStreaming(self, getImg=None, args=[]):
        """Starts the server and client threads"""
        if getImg:
            self.serverThread = ServerThread(self.SerBase, getImg, args)
        else:
            self.serverThread = ServerThread(self.SerBase, self.defaultCamFunc)

        self.clientThread = ClientThread(self.CliBase, self.frameQueue)

    # TODO: implement pausing via a listener on another thread
    # TODO: implement zerorpc here: now the
    def getCurrFrame(self):
        """Wrapper for framequeue get for zerorpc"""
        return self.frameQueue.get()

    def close(self, E=None, **kwargs):
        """Closes all: serverThread, clientThread, controlSock, CliBase, and SerBase"""
        destroy = kwargs.get("destroy", False)

        self.serverThread.join()
        self.clientThread.join()

        self.controlSock.close()
        try:
            self.SerBase.close(destroy=True)
            self.CliBase.close(destroy=True)
        except AttributeError:
            if destroy:
                del self.SerBase
                del self.CliBase

        if(E != None):
            print("Stream closed on Error\n" + str(E))
        else:
            self.log("Stream closed")

        if destroy:
            self.log("Deleting self")
            del self
