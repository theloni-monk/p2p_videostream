from . import streamclient
import cv2

demoClient = streamclient.Client("localhost", port=5000, verbose=True)


def startStream(Cli):
    """Decodes files from stream and displays them"""
    Cli.initializeStream()  # decode initial frame
    cv2.namedWindow("feed", cv2.WINDOW_NORMAL)

    while True:
        img = Cli.decodeFrame()  # decode frame

        cv2.imshow("feed", img)

        if cv2.waitKey(1) == 27:
            break  # esc to quit


startStream(demoClient)
