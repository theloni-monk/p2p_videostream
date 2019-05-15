from .. import VidStreamer
import cv2
import sys

if __name__ == '__main__':
    streamer= VidStreamer.VidStreamer(verbose = True, _diffmin = 0)
    streamer.set_partner(("10.50.3.181", 5000))
    streamer.initCam()
    streamer.cam.set_res(640,480)
    if not streamer.connectPartner(): 
        print("connectPartner failed")
        sys.exit(0)
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

