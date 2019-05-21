import socket

# for getting public ip:
from json import load
from urllib.request import urlopen
import ssl
# HACK: this makes the urllib requrest work for getting the public ip
ssl._create_default_https_context = ssl._create_unverified_context

import time
import random

# for async
from multiprocessing import Pool # for async connecting #TODO: optimize with threadpool
# NOTE: it would be better to use a ThreadPool but python is dumb and ThreadPool still isn't fully implemnted or documented 


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


class Partner:

	def __init__(self, **kwargs):
		
		self.verbose = kwargs.get("verbose", False)
		
		try:
			self.ip_public = load(urlopen('https://api.ipify.org/?format=json'))['ip']
		except Exception as e:
			self.log(str(e))
			raise Exception("No Internet connection available!")

		self.ip_local = get_localip()

		self.name = kwargs.get("name", "local_partner") + "." + self.ip_local.split(".")[-1] # make name unique

		self.partner_ip = kwargs.get("partner_ip", None)
		self.comm_port = kwargs.get("port", 5000)
		self.DNS_port =  kwargs.get("DNS_port", 8000)
		self.connected = False
		self.controlSock = None

		self.DNS_addr = kwargs.get("DNS_addr", "127.0.0.1")

	def log(self, m):
		if self.verbose:
			print(m)

	#TODO: rewrite with threading instead of async Pools
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
		csConnector_c.settimeout(timeout/4)

		stime = time.time()  # for chekcing for timeout

		conn = None
		clientAddr = None
		pool = Pool(processes=1)
		while True:
			serverReached = False
			try:
				accept_ret = pool.apply_async(csConnector_s.accept, ())  # accept async

			except Exception as e:
				self.log(e)
				raise e

			self.log("VidStreamer control sock connector serving")

			serverReached = False
			while True:

				if time.time() > stime + timeout:
					self.log("timed out")
					pool.close()
					pool.terminate()
					del pool  # i really dont want orphan processes
					return False  # return false on timeout

				self.log("VidStreamer control sock connector checking server for connection")
				try:
					serverReached = accept_ret.successful()  # see if the server was connected to
				except Exception:
					pass
				if serverReached:
					conn, clientAddr = accept_ret.get()
					break  # exit to the server logic

				# wait for a random amount of time
				# TODO: waittime should be more precise and computer specific
				waittime = random.randint(1, 700)/100
				wtime_end = time.time()+waittime
				self.log("VidStreamer control sock connector waiting")
				while time.time() < wtime_end:
					pass

				self.log("VidStreamer control sock connector checking server for connection")
				try:
					serverReached = accept_ret.successful()  # see if the server was connected to
				except Exception:
					pass
				if serverReached:
					conn, clientAddr = accept_ret.get()
					break  # exit to the server logic

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
					del pool  # i really dont want orphan processes
					csConnector_s.close()  # very important to close this
					self.controlSock = csConnector_c
					self.controlSock.settimeout(None)
					self.log("connectPartner success via connect!")
					return True

			if serverReached:  # if we got here it means the server was reached so the if is redundent but its more readable this way
				self.log("server reached")
				if clientAddr[0] == self.partner_ip:  # make sure we actually connect to our partner
					self.controlSock = conn
					self.clientAddr = clientAddr
					self.log('ControlSock, connected to ' +
							 self.clientAddr[0] + ':' + str(self.clientAddr[1]))
					self.connected = True
					del csConnector_c  # close open sockets
					self.log("connectPartner success via serving!")
					pool.close()
					pool.terminate()
					del pool  # i really dont want orphan processes
					return True  # only connects to one client

				# else implied
				conn.close()
				self.log('Refused connection to ' +
						 clientAddr[0] + ':' + str(clientAddr[1]))
				# this will return it to the top where it will do an async accept call again

	# this will break if you try non local DNS bc cox sucks
	
	def setDNS_local(self, dns_addr):
		self.DNS_addr = dns_addr[0]
		self.DNS_port = dns_addr[1]
	
	def connectDNS_local(self):
		try: self.QueryDNS_local("_")
		except: pass

	def QueryDNS_local(self, name_req):
		sock = socket.socket(socket.AF_INET)
		sock.settimeout(10)

		try: sock.connect((self.DNS_addr, self.DNS_port))
		except ConnectionRefusedError: raise Exception("Unreachable DNS_addr")

		try: 
			sock.send(self.name.encode())
			print("sent name to dns")
		except: #IDK what error this would be
			raise Exception("Sending name to DNS_local failed")

		try: 
			sock.send(name_req.encode())
			print("sent requested name to dns")
		except:
			raise Exception("Sending requested name to DNS_local failed")

		try:  
			addr = sock.recv(1024).decode()
			print("recieved data from dns: " + addr)
		except:
			raise Exception("DNS_local never sent requested data")
		
		if addr == "No User Found":
			raise Exception("No User Found")

		if addr[0] == "{":
			return addr

		addr = addr.split(",")
		addr[1] = int(addr[1])

		return addr

	def set_partner(self, addr):
		"""sets partner ip and port to given address"""
		self.partner_ip = addr[0]
		self.comm_port = addr[1]

	# TODO: create control command listener thread.
	def recv(self, size=1024):
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

	def send(self, message):
		# this is wrapper is basically only just so that this can be more readable
		self.controlSock.send(message)
