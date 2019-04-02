from .. import VidStreamer
import cv2
import sys

streamer= VidStreamer.VidStreamer("192.168.0.36", verbose = True)
if not streamer.connectPartner(): 
    print("connectPartner failed")
    sys.exit(0)
streamer.init_infoExchange()
streamer.initComps()
streamer.beginStreaming()
print("test1")
cv2.namedWindow("feed", cv2.WINDOW_NORMAL)

while True:
        img= streamer.getCurrFrame()
        cv2.imshow("feed", img)

        if cv2.waitKey(1) == 27:
            streamer.close(destroy=True)
            break  # esc to quit
