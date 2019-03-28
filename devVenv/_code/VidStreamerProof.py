import VidStreamer
import cv2

print("test1")
streamer= VidStreamer.VidStreamer("192.168.0.115")
streamer.connectPartner()
streamer.init_infoExchange()
streamer.initComps()
streamer.beginStreaming()
print("test2")
cv2.namedWindow("feed", cv2.WINDOW_NORMAL)

while True:
        img= streamer.getCurrFrame()
        cv2.imshow("feed", img)

        if cv2.waitKey(1) == 27:
            streamer.close(destroy=True)
            break  # esc to quit
