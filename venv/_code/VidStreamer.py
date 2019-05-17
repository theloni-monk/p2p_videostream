# p2p partner class:
from . import Partner

# multithreading:
import threading
from queue import Queue
from multiprocessing import Pool # for async connecting #TODO: optimize with threadpool
# NOTE: it would be better to use a ThreadPool but python is dumb and ThreadPool still isn't fully implemnted or documented

# streaming:
from .streambase import camera, streamserver, streamclient
import socket
import pickle

# misc:
import random
import time
import numba as nb


#TODO: implement flask rounting to webapp, or just use rpc to transfer the image to electron process

_DEBUG_0 = True

def _dlog(m):
	if _DEBUG_0:
		print(m)

#TODO: run this on a seperate process and optimize it with cpython
class ServerThread(threading.Thread):
	"""Thread that offloads initialization, encoding, and sending frames"""

	def __init__(self, vidserver, errorQ, frameFunc, frameFuncArgs=None):
		_dlog("TestST")
		threading.Thread.__init__(self)
		self.server = vidserver
		self.getFrame = frameFunc
		self.getFrameArgs = frameFuncArgs
		self._close_event=threading.Event()
		self.erQ=errorQ

	def close(self, E=None):
		self._close_event.set()
		if E: self.erQ.put(E)

	def is_closed(self):
		return self._close_event.is_set()

	def run(self):
		Er = None
		_dlog("serverThread begun running")

		# self.getFrame(self.getFrameArgs) is ugly but is how we get camera images
		if not self.server.isConnected:
			self.server.initializeStream(self.getFrame(self.getFrameArgs)) 
		_dlog("server in serverThread initialized")

		while True:
			if self.is_closed():
				_dlog("serverthread closing")
				return None
			else:
				try:
					self.server.sendFrame(self.getFrame(self.getFrameArgs), self.server._DIFFMIN) 
				#TODO: add some error handling here
				except Exception as e:
					_dlog("serverthread caught exception")
					Er = e
					break

		self.close(Er) # Thread always closes on error because worst case senario you can usually just spin up another thread

		#raise Er

#Note: this should run on a thread because it is less of a cpu bottleneck
class ClientThread(threading.Thread):
	"""Thread that offloads initialization, receiving, and decoding frames and puts them in given Queue"""

	def __init__(self, vidclient, fQueue, errorQ):
		_dlog("TestCT")
		threading.Thread.__init__(self)
		self.client = vidclient
		self.fQueue = fQueue
		self.erQ = errorQ
		self._close_event=threading.Event()

	def close(self, E=None):
		self._close_event.set()
		if E: self.erQ.put(E)

	def is_closed(self):
		return self._close_event.is_set()

	def run(self):
		Er = None
		_dlog("clientthread began running")
		self.client.initializeStream()
		_dlog("client in clientThread initialized")
		while True:
			if self.is_closed():
				_dlog("clienttrhead closing")
				return None
			else:
				try:
					self.fQueue.put(self.client.decodeFrame())
				except Exception as e:
					Er = e
					break
		
		self.close(Er)


class VSMetaData(): #TODO: make this more useful
	"""Wrapper for name, ip"""

	def __init__(self):
		self.name = None
		self.ip_public = None

class VidStreamer(Partner.Partner):
	"""VidStreamer is a wrapper for a client and a server with a control socket to connect to other vistreamers"""

	def __init__(self, **kwargs):

		self.verbose = kwargs.get("verbose", False)
		self.name = kwargs.get("name", "VidBot")
		self.cam = None

		# metadata setup
		self.selfMetaData = VSMetaData()
		self.selfMetaData.name = self.name

		self.pMetaData = None

		self.SerBase=None
		self.CliBase=None

		# TODO: support multiple clients
		self.serverThread = None
		self.clientThread = None

		self.frameQueue = Queue()
		self.errorQueue_s = Queue()
		self.errorQueue_c = Queue()

	def init_infoExchange(self):
		"""initial info exchange over controlsocket about things like name, resolution, and orientation via VidStreamerData struct"""
		# send metadata about self
		self.log(" ")
		try:
			# pickle.dumps serializes into a byte object instead of a file
			self.send(pickle.dumps(self.selfMetaData))
		except Exception as e:
			self.log("init_infoExchange failed to send data over controlSock")
			raise e

		self.log("Sent self.data")

		# recieve partner metadata
		try:
			# unserialize recieved metadata
			self.pMetaData = pickle.loads(self.recv(4096))
		except Exception as e:
			raise e
		self.log("recieved pMetaData, partner name: {}".format(self.pMetaData.name))

		# check if data is null:
		if self.pMetaData.name == None:
			self.close(Exception("Partner sent Null data for self.pData"))

	def initCam(self, resolution = (640, 480), **kwargs):
		"""basic func to delay camera initiation so that the camera light only goes on when it is being used \n kwargs: device/0"""
		self.cam = camera.Camera(device=kwargs.get("device", 0))
		self.cam.set_res(resolution[0], resolution[1])
		self.log("camera initalized")

	def initComps(self, **kwargs):
		""" initializes the server and client of the vidstreamer and connects them """
		self.log(" ")
		if not self.controlSock: self.connectPartner(kwargs.get("timeout", None))
		if not self.pMetaData: self.init_infoExchange()
		if not self.cam: self.initCam()

		# TODO: support multiple decoders
		self.CliBase = streamclient.Client(
			self.partner_ip, port=self.comm_port, verbose=self.verbose, elevateErrors=True)

		# TODO: support sending to multiple clients
		self.SerBase = streamserver.Server(
			self.partner_ip, port=self.comm_port, verbose=self.verbose, _diffmin = kwargs.get("_diffmin", 0), elevateErrors=True)
		
		asyncPool = Pool(processes=1) #TODO: use threads to do this instead of a process pool
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
		try: return self.cam.image
		except AttributeError: raise Exception("Camera never initalized")

	def beginStreaming(self, getImg=None, args=[]):
		"""Starts the server and client threads"""
		if getImg:
			self.serverThread = ServerThread(self.SerBase,  self.errorQueue_s, getImg, args)
		else:
			self.serverThread = ServerThread(self.SerBase, self.errorQueue_s, self.defaultCamFunc)

		self.clientThread = ClientThread(self.CliBase, self.frameQueue, self.errorQueue_c)
		
		self.serverThread.setName("VidStreamer Server_Thread")
		self.serverThread.start()

		self.clientThread.setName("VidStreamer Client0_Thread")
		self.clientThread.start()

	# TODO: implement pausing via a listener on another thread
	# TODO: implement zerorpc here:
	def getCurrFrame(self):
		"""Wrapper for framequeue get for zerorpc"""
		return self.frameQueue.get(block = True, timeout = 15)

	def close(self, E=None, **kwargs):
		"""Closes all: serverThread, clientThread, controlSock, CliBase, and SerBase"""
		destroy = kwargs.get("destroy", False)
		if self.serverThread:
			self.serverThread.close()
			self.serverThread.join()

		if self.clientThread:
			self.clientThread.close()
			self.clientThread.join()

		if self.controlSock:
			self.controlSock.close()

		try:
			self.SerBase.close(destroy=True)
			self.CliBase.close(destroy=True)
		except AttributeError: pass

		if(E != None):
			print("VidStreamer closed on Error\n" + str(E))
		else:
			self.log("VidStreamer closed")

		if destroy:
			self.log("Deleting self: VidStreamer. name = {}".format(self.name))
			del self
