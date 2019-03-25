from .streambase import *
import random
import time
# 
class VidStreamer:
    """vidstreamer is a wrapper for a client and a server with a control socket to connect to other vistreamers"""
    def __init__(self, target_ip, **kwargs):

        self.verbose=kwargs.get("verbose",False)
        self.name = kwargs.get("name", "VidBot")

        self.target_ip = target_ip
        #TODO: figure out how to check name after socket is connected
        self.target_name = kwargs.get("name", "default")
        self.comm_port = kwargs.get("port",8080)

        self.CliBase = Client(target_ip, port=self.comm_port, verbose = self.verbose)
        self.SerBase = Server(target_ip, port=self.comm_port, verbose = self.verbose)

        self.controlSockConnector = socket.socket()
        self.controlSockConnector.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        self.connected=False
        self.controlSock = None
    
    def log(self, m):
        """prints if self.verbose"""
        if self.verbose:
            print(m)


    def connectVidStreamer(timeout = None):
        """blocking, randomly switches between listening and attempting to connect to self.target_ip with a correct name
        Returns: False on timeout, True on connection"""
        stime=time.time()
        while True:
            connected=False
            ### Attempt to serve for a random amount of time:
            self.controlSockConnector.listen(10)
            self.controlSockConnector.settimeout(random.randint(50,100))
            conn, clientAddr = self.controlSockConnector.accept()

            #TODO: figure out how to check for the incoming name
            if clientAddr[0] == self.target_ip:
                    self.controlSock = conn
                    self.clientAddr = clientAddr
                    self.log('ControlSock, connected to ' +
                            self.clientAddr[0] + ':' + str(self.clientAddr[1]))
                    self.connected=True
                    return True  # only connects to one client
            #else:
            conn.close()
            self.log('Refused connection to ' +
                            clientAddr[0] + ':' + str(clientAddr[1]))
    
            ### Attempt to connect a random number of times:
            for i in range(random.randint(5,10)):
                try:
                    self.s.connect((self.target_ip, self.port))
                    connected=True
                except ConnectionRefusedError:
                    pass

                if connected:
                    self.connected=True
                    return True
            
            # Check for timeout:
            if timeout:
                if time.time() > stime + timeout:
                    return False

    def initComps(self):
        #FIXME: Write this to initialize the clinet and server once the controlsock is connected
