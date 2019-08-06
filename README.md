# Peer-to-Peer Video/Audio Streaming Project

## Peer-to-Peer Element

For the p2p element of the project I created a Partner class which can connect to another Partner by randomly switching between acting as a server and client while attempting to connect to the target partner ip. Because both partners are randomly switching between client and server when they inevitably get out-of-sync(one being a server and the other a client) a connection is established

Additionally I programmed a DNS class which stores (ip, name) pairs that have connected to it and can exchange said pairs with clients requesting an ip or a name.

## Video Element

For the video element of the project I used the libary rpistream (written by me and Ian Huang in 2018) which allows for a compressed video streaming server and a videoclient to be written in just a few lines. Most of the time on this element was spent integrating the library with the Partner class.

## Audio Element

The audio streaming element is comprised of a recording thread and a streaming thread. the recording thread records audio chunks into a queue which is then consumed by the streaming thread. The streaming thread then sends the audio chunks and ensures syncronyzation
