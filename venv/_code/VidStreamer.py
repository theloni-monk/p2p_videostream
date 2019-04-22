# multithreading:
import threading
from queue import Queue
from multiprocessing import Pool # for async connecting
# NOTE: it would be better to use a ThreadPool but python is dumb and ThreadPool still isn't fully implemnted or documented

# streaming:
from .streambase import *
import socket
import pickle

# misc:
import random
import time

# for getting public ip:
from json import load
from urllib.request import urlopen
import ssl
# HACK: this makes the urllib requrest work
ssl._create_default_https_context = ssl._create_unverified_context

_DEBUG_0 = True

def _dlog(m):
	if _DEBUG_0:
		print(m)


class ServerThread(threading.Thread):
	"""Thread that offloads initialization, encoding, and sending frames"""

	def __init__(self, vidserver, frameFunc, frameFuncArgs=None):
		_dlog("TestST")
		threading.Thread.__init__(self)
		self.server = vidserver
		self.getFrame = frameFunc
		self.getFrameArgs = frameFuncArgs

	def run(self):
		Er = None
		_dlog("serverThread begun running")

		# self.getFrame(self.getFrameArgs) is ugly but is how we get camera images
		self.server.initializeStream(self.getFrame(self.getFrameArgs)) 

		_dlog("server in serverThread initialized")
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
		_dlog("TestCT")
		threading.Thread.__init__(self)
		self.client = vidclient
		self.fQueue = fQueue

	def run(self):
		Er = None
		_dlog("clientthread began running")
		self.client.initializeStream()
		_dlog("client in clientThread initialized")
		while True:
			try:
				self.fQueue.put(self.client.decodeFrame())
			except Exception as e:
				Er = e
				break
		raise Er


class VSMetaData():
	"""Wrapper for name, ip, cameraResolution, and orientation"""

	def __init__(self):
		self.name = None
		self.ip_public = None
		self.cameraResolution = None
		self.orientation = None  # usesless for now


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

		# metadata setup
		self.selfMetaData = VSMetaData()
		self.selfMetaData.name = self.name
		try:
			self.selfMetaData.ip_public = load(
				urlopen('https://api.ipify.org/?format=json'))['ip']
		except Exception as e:
			print(str(e))
			raise Exception("No Internet connection available!")

		self.selfMetaData.cameraResolution = self.cam.resolution
		self.selfMetaData.orientation = True  # always horizontal for now

		self.pMetaData = None

		self.ip_local = get_localip()
		self.log("public ip: {}, local ip: {}".format(
			self.selfMetaData.ip_public, self.ip_local))
		self.partner_ip = partner_ip
		self.comm_port = kwargs.get("port", 5000)

		# TODO: support multiple decoders
		self.CliBase = streamclient.Client(
			partner_ip, port=self.comm_port, verbose=self.verbose)

		# TODO: support sending to multiple clients
		self.SerBase = streamserver.Server(
			partner_ip, port=self.comm_port, verbose=self.verbose)


		# TODO: support control command listening
		# self.isPaused = False  # NOTE: we can just keep streaming the same pause image

		# TODO: support multiple clients
		self.controlSock = None
		self.serverThread = None
		self.clientThread = None
		self.frameQueue = Queue()

	def log(self, m):
		"""prints if self.verbose"""
		if self.verbose:
			print(m)

	def connectPartner(self, timeout=30):
		"""blocking, randomly switches between listening and attempting to connect to self.partner_ip | 
		Returns: False on timeout, True on connection"""
		self.log("connectPartner called!")
		csConnector_s = socket.socket(socket.AF_INET)
		csConnector_s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		csConnector_s.bind((self.ip_local, self.comm_port))
		csConnector_s.listen(10)
		
		csConnector_c = socket.socket(socket.AF_INET)
		csConnector_c.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		csConnector_c.settimeout(timeout/2)

		stime = time.time() # for chekcing for timeout

		conn = None
		clientAddr = None
		pool = Pool(processes=1)
		while True:
			serverReached=False
			try:
				accept_ret = pool.apply_async(csConnector_s.accept, ())  # accept async HOPEFULLY

			except Exception as e:
				self.log(e)
				raise e

			self.log("VidStreamer control sock connector serving")

			serverReached=False
			while True:

				if time.time() > stime + timeout:
					self.log("timed out")
					return False # return false on timeout

				self.log("VidStreamer control sock connector checking server for connection")
				try:
					serverReached = accept_ret.successful()  # see if the server was connected to
				except Exception:
					pass
				if serverReached:
					conn, clientAddr = accept_ret.get()
					break # exit to the server logic


				# wait for a random amount of time 
				# TODO: waittime should be more precise and computer specific
				waittime = random.randint(1, 150)/10	
				wtime_end = time.time()+waittime
				self.log("VidStreamer control sock connector waiting")
				while time.time() < wtime_end:
					pass

				
				# if the server wasn't reached try to connect to the partner
				self.log("VidStreamer control sock connector attempting connection")
				connected = False

				try:
						csConnector_c.connect((self.partner_ip, self.comm_port))
						connected = True

				except ConnectionRefusedError:
						self.log("Connection to partner refused")
						connected = False
				except OSError as e:  # HACK
						self.log("encountered OSError: {}".format(e))
						connected = False

				if connected and not conn:
					pool.terminate()
					pool.close()
					pool.join()
					del pool # i really dont want orphan processes
					csConnector_s.close()  # very important to close this
					self.controlSock = csConnector_c  
					self.controlSock.settimeout(None)
					self.log("connectPartner success via connect!")
					return True

			if serverReached:  # if we got here it means the server was reached so the if is redundent but its more readable this way
				self.log("server reached")
				if clientAddr[0] == self.partner_ip: # make sure we actually connect to our partner
					self.controlSock = conn
					self.clientAddr = clientAddr
					self.log('ControlSock, connected to ' +
							 self.clientAddr[0] + ':' + str(self.clientAddr[1]))
					self.connected = True
					del csConnector_c  # close open sockets
					self.log("connectPartner success via serving!")
					pool.close()
					pool.terminate()
					del pool # i really dont want orphan processes
					return True  # only connects to one client

				# else implied
				conn.close()
				self.log('Refused connection to ' +
						 clientAddr[0] + ':' + str(clientAddr[1]))
				# this will return it to the top where it will do an async accept call again

	# TODO: create control command listener thread.
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

	def cSockSend(self, message):
		# this is wrapper is basically only just so that this can be more readable
		self.controlSock.send(message)

	def init_infoExchange(self):
		"""initial info exchange over controlsocket about things like name, resolution, and orientation via VidStreamerData struct"""
		# send metadata about self
		self.log(" ")
		try:
			# pickle.dumps serializes into a byte object instead of a file
			self.cSockSend(pickle.dumps(self.selfMetaData))
		except Exception as e:
			self.log("init_infoExchange failed to send data over controlSock")
			raise e

		self.log("Sent self.data")

		# recieve partner metadata
		try:
			# unserialize recieved metadata
			self.pMetaData = pickle.loads(self.cSockRecv(4096))
		except Exception as e:
			raise e
		self.log("recieved pMetaData, partner name: {}".format(self.pMetaData.name))

		# check if data is null:
		if self.pMetaData.name == None:
			self.close(Exception("Partner sent Null data for self.pData"))

	def initComps(self, **kwargs):
		""" initializes the server and client of the vidstreamer and connects them """
		self.log(" ")
		if not self.controlSock: self.connectPartner(kwargs.get("timeout", None))
			
		if not self.pMetaData: self.init_infoExchange()

		asyncPool = Pool(processes=1)
		self.SerBase.initializeSock()
		serve_ret = asyncPool.apply_async(self.SerBase.serve,(True,))

		self.CliBase.initializeSock()
		self.CliBase.connectSock()
		self.SerBase.clientAddr, self.SerBase.conn = serve_ret.get()
		asyncPool.close()
		asyncPool.join()
		_dlog("dlog1: "+str(self.SerBase.clientAddr))
		del asyncPool	

	def defaultCamFunc(self, *args):
		"""Funcional wrapper for self.cam.image @property"""
		return self.cam.image

	def beginStreaming(self, getImg=None, args=[]):
		"""Starts the server and client threads"""
		if getImg:
			self.serverThread = ServerThread(self.SerBase, getImg, args)
		else:
			self.serverThread = ServerThread(self.SerBase, self.defaultCamFunc)

		self.clientThread = ClientThread(self.CliBase, self.frameQueue)
		
		self.serverThread.setName("Server_Thread")
		self.serverThread.start()

		self.clientThread.setName("Client0_Thread")
		self.clientThread.start()

	# TODO: implement pausing via a listener on another thread
	# TODO: implement zerorpc here:
	def getCurrFrame(self):
		"""Wrapper for framequeue get for zerorpc"""
		return self.frameQueue.get()

	def close(self, E=None, **kwargs):
		"""Closes all: serverThread, clientThread, controlSock, CliBase, and SerBase"""
		destroy = kwargs.get("destroy", False)
		if self.serverThread:
			self.serverThread.join()
		if self.clientThread:
			self.clientThread.join()

		if self.controlSock:
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
