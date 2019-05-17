from .. import AudioStreamer
import sys
import cv2

if __name__ == "__main__":
    streamer= AudioStreamer.AudioStreamer(verbose = True, _diffmin = 0)
    streamer.set_partner(("192.168.0.241", 5000))
    if not streamer.connectPartner(): 
        print("connectPartner failed")
        sys.exit(0)
    
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