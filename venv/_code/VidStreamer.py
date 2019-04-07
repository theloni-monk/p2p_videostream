from .streambase import *
import socket
import random
import time
import pickle

# for getting public ip:
from json import load
from urllib.request import urlopen
import ssl
ssl._create_default_https_context = ssl._create_unverified_context # HACK: this makes the urllib requrest work

# for accessing stream data
import threading
from queue import Queue



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
        self.ip_public = None
        self.cameraResolution = None
        self.orientation = None  # usesless for now

DEBUG_0=True

def get_localip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

class VidStreamer:
    """VidStreamer is a wrapper for a client and a server with a control socket to connect to other vistreamers"""

    def __init__(self, partner_ip, **kwargs):

        self.verbose = kwargs.get("verbose", False)
        self.name = kwargs.get("name", "VidBot")
        self.cam = camera.Camera()

        # datastruct setup
        self.vsData = VidStreamerData()
        self.vsData.name = self.name
        try:
            self.vsData.ip_public = load(
                urlopen('https://api.ipify.org/?format=json'))['ip']
        except Exception as e:
            print(str(e))
            raise Exception("No Internet connection available!")

        self.vsData.cameraResolution = self.cam.resolution
        self.vsData.orientation = True  # always horizontal for now

        self.pData = None

        self.ip_local=get_localip()
        self.partner_ip = partner_ip
        self.comm_port = kwargs.get("port", 8080)

        self.CliBase = streamclient.Client(
            partner_ip, port=self.comm_port, verbose=self.verbose)
        self.SerBase = streamserver.Server(
            partner_ip, port=self.comm_port, verbose=self.verbose)

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
    
    def Dlog(self, m):
        if DEBUG_0: print(m)

    def connectPartner(self, timeout = 30):
        """blocking, randomly switches between listening and attempting to connect to self.partner_ip with a correct name
        Returns: False on timeout, True on connection"""
        
        csConnector_s = socket.socket(socket.AF_INET)
        csConnector_s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        csConnector_s.bind((self.ip_local), self.comm_port)) 
        csConnector_s.setblocking(0)
            
        csConnector_c = socket.socket(socket.AF_INET)
        csConnector_c.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Attempt to serve for a random amount of time:
        csConnector_s.listen(10)
        csConnector_s.settimeout(15)

        stime = time.time()

        connected = False
        conn = None
        while True:
            try:
                conn, clientAddr = csConnector_s.accept()
            except Exception as e:
                self.log(e)
        
            if conn:  # wait for the async connector
                if clientAddr[0] == self.partner_ip:
                    
                    self.controlSock = conn #FIXME: not sure if this will get destroyed when scope is left
                    self.clientAddr = clientAddr
                    self.log('ControlSock, connected to ' +
                             self.clientAddr[0] + ':' + str(self.clientAddr[1]))
                    self.connected = True
                    csConnector_c.shutdown()
                    csConnector_c.close() # not needed
                    return True  # only connects to one client
                # else implied
                conn.close()
                self.log('Refused connection to ' +
                         clientAddr[0] + ':' + str(clientAddr[1]))
                break # serve again
            
            #TODO: make sure this works and the partners actually are on the same socket
            else: # if we haven't gotten a connection servingattempt to connect
                connectTries = 5 # tuning var
                for i in range(connectTries):
                    try:
                        if not conn:
                            csConnector_c.connect((self.partner_ip, self.comm_port))
                            connected = True
                    except ConnectionRefusedError:
                        self.log("Connection to partner refused")
                        connected = False
                    except OSError as e: #HACK
                        self.Dlog("encountered OSError: {}".format(e))
                        connected = False

                    if connected:
                        # im worried how quickly this will happen:
                        csConnector_s.shutdown()
                        csConnector_s.close() # very important to close this
                        self.controlSock =  csConnector_c #FIXME: not sure if this will be destroyed
                        self.connected = True
                        return True

            # Check for timeout:
            if timeout:
                if time.time() - stime > timeout:
                    self.log("connectPartner timed out")
                    csConnector_c.close()
                    csConnector_s.close()
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
            netutils.send_msg(self.controlSock, pickle.dump(self.vsData))
        except Exception as e:
            self.log("init_infoExchange failed to send data over controlSock")
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
        if self.serverThread: self.serverThread.join()
        if self.clientThread: self.clientThread.join()
        
        if self.controlSock: self.controlSock.close()
        
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
