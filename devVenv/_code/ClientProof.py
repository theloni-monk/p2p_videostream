from streambase import streamclient
client = streamclient.Client(serverIp="localhost", port=5000, verbose=True)
client.startStream()
