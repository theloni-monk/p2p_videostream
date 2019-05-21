from . import VidStreamer
from . import AudioStreamer
from . import DNS_local

import cv2
import _thread
import sys

def runVidStreamer(streamer):
    streamer.init_infoExchange()
    streamer.initComps()
    streamer.beginStreaming()
    print("test1")
    cv2.namedWindow("feed", cv2.WINDOW_NORMAL)

    while True:
            if not streamer.errorQueue_c.empty():
                print("\nclientThread closed on error: {}\n".format(streamer.errorQueue_c.get(block=True, timeout= 2)))
                streamer.close(destroy = True)
                break

            if cv2.waitKey(1) == 27:
                streamer.close(destroy = True)
                break  # esc to quit
            
            img= streamer.getCurrFrame()
            cv2.imshow("feed", img)

def runAStreamer(streamer):
    streamer.init_infoExchange()
    streamer.beginStreaming()
    print("test1")
    while True:
            if not streamer.errorQueue_c.empty():
                print("\nclientThread closed on error: {}\n".format(streamer.errorQueue_c.get(block=True, timeout= 2)))
                break
            if not streamer.errorQueue_p.empty():
                print("\nplayerThread closed on error: {}\n".format(streamer.errorQueue_p.get(block=True, timeout= 2)))
                break

            if cv2.waitKey(1) == 27:
                break  # esc to quit
    streamer.close(destroy = True)

if __name__ == '__main__':
    dns = DNS_local.DNS_local()
    dns.begin()
    dns_addr = ("127.0.0.1", 8000) # edit

    print("intializing...")
    
    if input("ready to begin? ") == "yes": pass #really just wait for both to be on the dns
    n = input("input name: ")
    streamer= VidStreamer.VidStreamer(verbose = False, name = n)
    Astreamer= AudioStreamer.AudioStreamer(verbose = False, name = n)

    streamer.setDNS_local(dns_addr)
    streamer.connectDNS_local()

    userdict=eval(streamer.QueryDNS_local("GET_ALL_USERS"))
    print("Available Partners connected on network: \n")
    print([*userdict]) # print keys of dict

    escape = False
    while not escape:
        name = input("Who would you like to connect to? ")
        try: 
            pIp = userdict[name]
            escape = True
        except KeyError:
            print("Sorry that name doesn't exist")

    Astreamer.set_partner((pIp, 7000))
    while not Astreamer.connectPartner(): 
        print("ConnectPartner failed for AudioStreamer")
    _thread.start_new_thread(runAStreamer, (Astreamer,))

    streamer.set_partner((pIp, 6000))
    streamer.initCam()
    streamer.cam.set_res(640,480)
    while not streamer.connectPartner(): 
        print("ConnectPartner failed for VidStreamer")
        sys.exit(0)
    runVidStreamer(streamer)
