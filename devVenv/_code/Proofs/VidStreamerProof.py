from ..VidStreamer import *
import cv2

streamer=VidStreamer("10.50.5.8")
streamer.connectPartner()
streamer.init_infoExchange()
streamer.initComps()
streamer.beginStreaming()

cv2.namedWindow("feed", cv2.WINDOW_NORMAL)

while True:
        img=streamer.getCurrFrame
        cv2.imshow("feed", img)

        if cv2.waitKey(1) == 27:
            break  # esc to quit