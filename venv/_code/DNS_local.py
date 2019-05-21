import socket
from .streambase import netutils
from queue import Queue
from threading import Thread

"""
userdict looks like this:
{'name', [addr, port]}
"""
userdict = {}
threadlist = []
_stop = False

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

def _runserver(socket):

    socket.settimeout(10)
    try:
        name = socket.recv(1024).decode().split(".", [0]) # remove .### on the end of name
    except TimeoutError:
        return False

    # add new connected users to userdict
    try: userdict[name] 
    except KeyError: userdict[name] = socket.getsockname()

    # the client requests a name
    try:
        name_req = socket.recv(1024).decode()
    except TimeoutError:
        return False


    if name_req == "GET_ALL_USERS":
        socket.send(str(userdict).encode())
        return True

    # try to send the associated name
    try:
        out_addr = userdict[name_req]
    except KeyError:
        socket.send("No User Found".encode())
        return False

    clean_addr = str(out_addr).replace("(","").replace(")","").replace("'","")
    #NOTE: clean_addr looks like: "xxx.xxx.xxx.xxx, ####"
    socket.send(clean_addr.encode())

    return True

def _beginServing(localip, port):
    s = socket.socket(socket.AF_INET)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.settimeout(5)
    s.bind((localip, port))
    s.listen(10)

    while True:
        if _stop: return None

        try: client = s.accept()[0]
        except TimeoutError: pass

        T = Thread(target = _runserver, args = (client,))
        threadlist.append(T)
        T.start()

class DNS_local():
    def __init__(self, **kwargs):
        """Default port 8000"""
        #self.userdict = {}
        self.verbose = kwargs.get("verbose", False)
        self.localip =  get_localip()
        self.mainThread = None
        self.port = kwargs.get("port", 8000)
    
    def log(self,m):
        if self.verbose: print(m)

    def begin(self):
        # this might not be a thing
        self.mainThread = Thread(target = _beginServing, args = (self.localip, self.port,))
        threadlist.append(self.mainThread)
        self.mainThread.start()
        self.log("DNS started with IP:{} on port: {}".format(self.localip, self.port))

    def close(self):
        self.log("closing")
        _stop = True
        for t in threadlist:
            t.join()
        self.log("DNS closed")


