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

import pyaudio #TODO: install pyaudio
import socket
from threading import Thread

_DEBUG_0 = True

def _dlog(m):
	if _DEBUG_0:
		print(m)

#TODO: rewrite these
#NOTE: make sure there is a buffer of audio chunks

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 2
RATE = 44100


sframes = [] 
def record(stream):    #FIXME: unsafe
		while True:
			try:
				sframes.append(stream.read(CHUNK))
				_dlog("read mic stream frame")
			except OSError: 
				_dlog("encountered OSError in record")
				PyHandle = pyaudio.PyAudio()
				PyHandle.open(format = FORMAT,
					channels = CHANNELS,
					rate = RATE,
					input = True,
					frames_per_buffer = CHUNK,
				)

class ServerThread(threading.Thread):
	"""Thread that offloads initialization, encoding, and sending frames"""

	def __init__(self, addr, errorQ):
		_dlog("TestST")
		threading.Thread.__init__(self)
		self.ip = addr[0]
		self.port = addr[1]
		self._close_event=threading.Event()
		self.erQ=errorQ
		
		self.PyHandle = pyaudio.PyAudio()

		self.stream = self.PyHandle.open(format = FORMAT,
					channels = CHANNELS,
					rate = RATE,
					input = True,
					frames_per_buffer = CHUNK,
					)
		
		self.RT = Thread(target = record, args = (self.stream,))
		self.RT.start()

	def close(self, E=None):
		self._close_event.set()
		if E: self.erQ.put(E)

	def is_closed(self):
		return self._close_event.is_set()


	def run(self):
		Er = None
		_dlog("serverThread begun running")

		udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)    
		while True:
			if self.is_closed():
				_dlog("serverthread closing")
				return None
			if len(sframes) > 0:
				try: 
					udp.sendto(sframes.pop(0), (self.ip, self.port))
					_dlog("sent audio frame")
				except Exception as e:
					print(e)
					Er = e
					break


		self.close(Er)
		udp.close()


class ClientThread(threading.Thread):
	"""Thread that offloads initialization, receiving, and decoding frames and puts them in given Queue"""

	def __init__(self, addr, fQueue, errorQ):
		_dlog("TestCT")
		threading.Thread.__init__(self)
		self.ip = addr[0]
		self.port = addr[1]
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
		udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		udp.bind((self.ip, self.port))

		while True:
			if self.is_closed():
				_dlog("clienttrhead closing")
				return None
			try: 
				soundData, addr = udp.recvfrom(CHUNK * CHANNELS * 2)
				_dlog("recieved audio frame")
			except Exception as e:
				_dlog(e)
				Er = e
				break
			self.fQueue.put(soundData)
		
		self.close(Er)
		udp.close()

class PlayerThread(threading.Thread):
	
	def __init__(self, frameQ, errorQ):
		_dlog("TestPT")
		threading.Thread.__init__(self)
		self._close_event=threading.Event()
		self.erQ=errorQ
		
		self.PyHandle = pyaudio.PyAudio()

		self.stream = self.PyHandle.open(format = FORMAT,
					channels = CHANNELS,
					rate = RATE,
					output = True,
					frames_per_buffer = CHUNK,
					)

		self.frameQ = frameQ
	
	def close(self, E=None):
		self._close_event.set()
		if E: self.erQ.put(E)
		self.stream.close()

	def is_closed(self):
		return self._close_event.is_set()


	def run(self):
		BUFFER = 10
		Er = None
		while True:
			if self.is_closed():
				_dlog("serverthread closing")
				return None

			if self.frameQ.qsize() == BUFFER:
				if self.is_closed():
					_dlog("serverthread closing")
					return None
				
				while True:
					try:
						self.stream.write(self.frameQ.get(), CHUNK)
						_dlog("played audio frame")
					except Exception as e:
						_dlog(e)
						Er = e
					if Er: break
				if Er: break

		self.close(Er)


class ASMetaData: #TODO: make this more useful
	"""Wrapper for name, ip"""
	def __init__(self):
		self.name = None
		self.ip_public = None

class AudioStreamer(Partner.Partner):
	
	def __init__(self, **kwargs):
		super().__init__(**kwargs)

		# metadata setup
		self.selfMetaData = ASMetaData()
		self.selfMetaData.name = self.name

		self.pMetaData = None

		# TODO: support multiple clients
		self.serverThread = None
		self.clientThread = None
		self.playerThread = None

		self.frameQueue = Queue()
		self.errorQueue_s = Queue()
		self.errorQueue_c = Queue()
		self.errorQueue_p = Queue()
	
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

	#NOTE: Unecessary
	def initcomp(self, **kwargs):
		if not self.controlSock: self.connectPartner(kwargs.get("timeout", None))
		if not self.pMetaData: self.init_infoExchange()
	
	def beginStreaming(self, player = True):
		self.serverThread = ServerThread((self.partner_ip,self.comm_port+1), self.errorQueue_s)
		self.clientThread = ClientThread((self.ip_local,self.comm_port+1), self.frameQueue, self.errorQueue_c)
		if player: self.playerThread = PlayerThread(self.frameQueue, self.errorQueue_p )
		
		self.serverThread.setName("AudioStreamer Server0_Thread")
		self.clientThread.setName("AudioStreamer Client0_Thread")
		if player: self.playerThread.setName("AudioStreamer Player0_Thread")
		
		self.serverThread.start()
		self.clientThread.start()
		if player: self.playerThread.start()

	def close(self, E=None, **kwargs):
		"""Closes all: serverThread, clientThread, controlSock, CliBase, and SerBase"""
		destroy = kwargs.get("destroy", False)
		if self.serverThread:
			self.serverThread.close()
			self.serverThread.join()

		if self.clientThread:
			self.clientThread.close()
			self.clientThread.join()
		
		if self.playerThread:
			self.playerThread.close()
			self.playerThread.join()
		
		if self.controlSock:
			self.controlSock.close()

		if(E != None):
			print("AudioStreamer closed on Error\n" + str(E))
		else:
			self.log("AudioStreamer closed")

		if destroy:
			self.log("Deleting self: AudioStreamer. name = {}".format(self.name))
			del self


