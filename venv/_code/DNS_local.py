import socket
from .streambase import netutils
from queue import Queue
import _thread

"""
userdict looks like this:
{'name', [addr, port]}
"""
userdict = {}

# no need for a threadList bc all threads will time out

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

def runserver(socket):

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

    # try to send the associated name
    try:
        out_addr = userdict[name_req]
    except KeyError:
        socket.send("No User Found".encode())
        return False

    clean_addr = str(out_addr).replace("(","").replace(")","").replace("'","")
    socket.send(clean_addr.encode())

    return True

def beginServing(localip):
    s = socket.socket(socket.AF_INET)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.settimeout(5)
    s.bind(localip)
    s.listen(10)

    while True:
        client = s.accept()[0]
        _thread.start_new_thread( runserver, (client,) )

class DNS_local():
    def __init__(self):
        #self.userdict = {}
        self.localip =  get_localip()
        self.mainThread = None

    def begin(self):
        # this might not be a thing
        self.mainThread = _thread.start_new_thread( beginServing, (self.localip,) )
        
        print("DNS started with IP:{}".format(self.localip))

    def close(self):
        del self # joins threads?

       




    