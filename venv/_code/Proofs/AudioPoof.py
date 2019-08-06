from .. import AudioStreamer
import sys
import cv2

if __name__ == "__main__":
    streamer= AudioStreamer.AudioStreamer(verbose = True, _diffmin = 0)
    streamer.set_partner(("192.168.0.36", 5000))
    if not streamer.connectPartner(): 
        print("connectPartner failed")
        sys.exit(0)
    
    streamer.init_infoExchange()
    streamer.beginStreaming()
    print("test1")
    Er=None
    while True:
            if not streamer.errorQueue_c.empty():
                Er = streamer.errorQueue_c.get(block=True, timeout= 2)
                print("\nclientThread closed on error: {}\n".format(Er))
                break
            if not streamer.errorQueue_p.empty():
                Er = streamer.errorQueue_p.get(block=True, timeout= 2)
                print("\nplayerThread closed on error: {}\n".format(Er))
                break

            if cv2.waitKey(1) == 27:
                break  # esc to quit

    streamer.close(Er)