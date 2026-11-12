import time

import numpy as np
import pyqtgraph as pg
from qtpy import QtWidgets
from ScopeFoundry import Measurement


class WebcamLiveMeasure(Measurement):
    """
    ScopeFoundry Measurement providing a live viewer and snapshot saver
    for the WebcamZmqHW hardware component.
    """

    name = "webcam_live"

    def setup(self):
        self.display_update_period = 0.04  # 25 Hz UI refresh

        S = self.settings
        S.New(
            "auto_levels",
            dtype=bool,
            initial=False,
            description="Automatically scale image intensity levels on each update",
        )
        S.New(
            "save_h5_on_stop",
            dtype=bool,
            initial=False,
            description="Save the last captured frame to HDF5 when measurement stops",
        )

        self.data = {
            "image": np.zeros((480, 640, 3), dtype=np.uint8),
            "frame_id": 0,
            "timestamp": 0.0,
        }

        self.add_operation("snap_h5", self.snap_h5, description="Save current frame to HDF5")

    def setup_figure(self):
        hw = self.app.hardware["webcam_zmq"]

        # Top control bar
        cb_layout = QtWidgets.QHBoxLayout()
        cb_layout.addWidget(self.new_start_stop_button())
        cb_layout.addWidget(
            self.settings.New_UI(
                exclude=("activation", "run_state", "profile", "progress")
            )
        )
        snap_btn = self.operations.new_button("snap_h5")
        cb_layout.addWidget(snap_btn)

        header_widget = QtWidgets.QWidget()
        header_layout = QtWidgets.QVBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.addLayout(cb_layout)

        # PyQtGraph live image canvas
        self.graphics_widget = pg.GraphicsLayoutWidget(border=(100, 100, 100))
        self.img_plot = self.graphics_widget.addPlot(title="Webcam Live Stream")
        self.img_plot.setAspectLocked(True)
        self.img_plot.getViewBox().invertY(True)

        self.img_item = pg.ImageItem(axisOrder="row-major")
        self.img_plot.addItem(self.img_item)

        self.hist_lut = pg.HistogramLUTItem()
        self.hist_lut.setImageItem(self.img_item)
        self.graphics_widget.addItem(self.hist_lut)

        # Hardware settings panel alongside image
        hw_controls = hw.new_control_widgets(title="Webcam & ZMQ PUB Settings")
        hw_controls.setMaximumWidth(320)

        body_layout = QtWidgets.QHBoxLayout()
        body_layout.addWidget(self.graphics_widget, stretch=1)
        body_layout.addWidget(hw_controls, stretch=0)

        self.ui = QtWidgets.QWidget()
        self.layout = QtWidgets.QVBoxLayout(self.ui)
        self.layout.addWidget(header_widget)
        self.layout.addLayout(body_layout, stretch=1)

    def run(self):
        hw = self.app.hardware["webcam_zmq"]
        if not hw.settings["connected"]:
            hw.settings["connected"] = True
            time.sleep(0.2)

        while not self.interrupt_measurement_called:
            frame, meta = hw.get_latest_frame()
            if frame is not None and meta is not None:
                self.data["image"] = frame
                self.data["frame_id"] = meta["frame_id"]
                self.data["timestamp"] = meta["timestamp"]
            time.sleep(0.02)

        if self.settings["save_h5_on_stop"]:
            self.save_h5(data=self.data)

    def snap_h5(self):
        """Save the latest frame immediately to an HDF5 file."""
        hw = self.app.hardware["webcam_zmq"]
        frame, meta = hw.get_latest_frame()
        if frame is not None and meta is not None:
            self.data["image"] = frame
            self.data["frame_id"] = meta["frame_id"]
            self.data["timestamp"] = meta["timestamp"]
        self.save_h5(data=self.data)
        self.log.info(f"Saved snapshot frame #{self.data['frame_id']} to HDF5")

    def update_display(self):
        img = self.data.get("image")
        if img is None:
            return

        auto_levels = bool(self.settings["auto_levels"])
        self.img_item.setImage(img, autoLevels=auto_levels)
        if not auto_levels and img.dtype == np.uint8:
            self.img_item.setLevels([0, 255])

        hw = self.app.hardware["webcam_zmq"]
        S = hw.settings
        pub_state = (
            f"PUB {S['zmq_bind_address']} [{S['zmq_topic']}]"
            if S["stream_enabled"]
            else "PUB paused"
        )
        self.img_plot.setTitle(
            f"Webcam Live | Frame #{self.data['frame_id']} | "
            f"{img.shape[1]}x{img.shape[0]} {S['color_mode']} | "
            f"{S['fps_measured']:.1f} FPS | {pub_state}"
        )
