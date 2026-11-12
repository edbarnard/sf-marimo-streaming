import sys

from ScopeFoundry import BaseMicroscopeApp

from webcam_live_measure import WebcamLiveMeasure
from webcam_zmq_hw import WebcamZmqHW


class WebcamStreamApp(BaseMicroscopeApp):
    """
    ScopeFoundry application with a webcam capture + ZMQ PUB streaming
    hardware component and a live preview measurement.
    """

    name = "webcam_stream_app"

    def setup(self):
        self.add_hardware(WebcamZmqHW(self))
        self.add_measurement(WebcamLiveMeasure(self))


def main():
    app = WebcamStreamApp(sys.argv)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
