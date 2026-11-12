"""
Convert `sf_marimo_slide_deck.md` (plus Marimo cell visual outputs from `red_channel_viewer.py`)
into a widescreen (16:9) PowerPoint presentation (`sf_marimo_slide_deck.pptx`).
"""

import io
import shutil
from pathlib import Path

import cv2
import numpy as np
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt


# Theme palette
BG_DARK = RGBColor(15, 23, 42)        # #0F172A
CARD_BG = RGBColor(30, 41, 59)        # #1E293B
NODE_BG = RGBColor(15, 23, 42)        # #0F172A
CODE_BG = RGBColor(17, 24, 39)        # #111827
BORDER_CLR = RGBColor(71, 85, 105)    # #475569
TEXT_WHITE = RGBColor(248, 250, 252)  # #F8FAFC
TEXT_MUTED = RGBColor(148, 163, 184)  # #94A3B8
ACCENT_RED = RGBColor(239, 68, 68)    # #EF4444
ACCENT_BLUE = RGBColor(56, 189, 248)  # #38BDF8
ACCENT_TEAL = RGBColor(45, 212, 191)  # #2DD4BF
ACCENT_GOLD = RGBColor(250, 204, 21)  # #FACC15
ACCENT_PURPLE = RGBColor(192, 132, 252)  # #C084FC


def set_slide_background(slide, color: RGBColor = BG_DARK):
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = color


def add_header(slide, title_text: str, subtitle_text: str = "", badge_text: str = ""):
    bar = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(0.08)
    )
    bar.fill.solid()
    bar.fill.fore_color.rgb = ACCENT_RED
    bar.line.fill.background()

    if badge_text:
        badge = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(0.55),
            Inches(0.22),
            Inches(3.4),
            Inches(0.30),
        )
        badge.fill.solid()
        badge.fill.fore_color.rgb = CARD_BG
        badge.line.color.rgb = ACCENT_BLUE
        tf_b = badge.text_frame
        tf_b.word_wrap = False
        p_b = tf_b.paragraphs[0]
        p_b.text = badge_text.upper()
        p_b.font.size = Pt(9.5)
        p_b.font.bold = True
        p_b.font.color.rgb = ACCENT_BLUE
        p_b.alignment = PP_ALIGN.CENTER

    title_top = Inches(0.56) if badge_text else Inches(0.28)
    tb = slide.shapes.add_textbox(Inches(0.55), title_top, Inches(12.2), Inches(0.75))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title_text
    p.font.size = Pt(24)
    p.font.bold = True
    p.font.color.rgb = TEXT_WHITE

    if subtitle_text:
        p2 = tf.add_paragraph()
        p2.text = subtitle_text
        p2.font.size = Pt(12.5)
        p2.font.color.rgb = TEXT_MUTED


def add_box(
    slide,
    left: float,
    top: float,
    width: float,
    height: float,
    title: str,
    lines: list[str] | None = None,
    bg_color: RGBColor = CARD_BG,
    border_color: RGBColor = ACCENT_BLUE,
    title_color: RGBColor | None = None,
    title_size: int = 13,
    body_size: int = 11,
    align=PP_ALIGN.LEFT,
):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(left),
        Inches(top),
        Inches(width),
        Inches(height),
    )
    shape.adjustments[0] = 0.03
    shape.fill.solid()
    shape.fill.fore_color.rgb = bg_color
    shape.line.color.rgb = border_color
    shape.line.width = Pt(1.5)

    tf = shape.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.16)
    tf.margin_right = Inches(0.16)
    tf.margin_top = Inches(0.12)
    tf.margin_bottom = Inches(0.10)

    p0 = tf.paragraphs[0]
    p0.text = title
    p0.font.size = Pt(title_size)
    p0.font.bold = True
    p0.font.color.rgb = title_color or border_color
    p0.alignment = align
    if lines:
        p0.space_after = Pt(5)
        for line in lines:
            p = tf.add_paragraph()
            p.text = line
            p.font.size = Pt(body_size)
            p.font.color.rgb = TEXT_WHITE
            p.alignment = align
            p.space_after = Pt(3)
    return shape


def add_code_box(
    slide,
    left: float,
    top: float,
    width: float,
    height: float,
    header_label: str,
    code_str: str,
    font_size: int = 10,
):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(left),
        Inches(top),
        Inches(width),
        Inches(height),
    )
    shape.adjustments[0] = 0.02
    shape.fill.solid()
    shape.fill.fore_color.rgb = CODE_BG
    shape.line.color.rgb = BORDER_CLR
    shape.line.width = Pt(1.0)

    tf = shape.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.16)
    tf.margin_right = Inches(0.16)
    tf.margin_top = Inches(0.12)
    tf.margin_bottom = Inches(0.10)

    p_hdr = tf.paragraphs[0]
    p_hdr.text = header_label
    p_hdr.font.size = Pt(10.5)
    p_hdr.font.bold = True
    p_hdr.font.color.rgb = ACCENT_GOLD
    p_hdr.space_after = Pt(5)

    for line in code_str.strip("\n").splitlines():
        p = tf.add_paragraph()
        p.text = line if line else " "
        p.font.name = "Courier New"
        p.font.size = Pt(font_size)
        p.font.color.rgb = RGBColor(226, 232, 240)
        p.space_after = Pt(1)


def add_arrow_banner(
    slide,
    left: float,
    top: float,
    width: float,
    height: float,
    label: str,
    color: RGBColor = ACCENT_GOLD,
    shape_type=MSO_SHAPE.RIGHT_ARROW,
):
    arr = slide.shapes.add_shape(
        shape_type,
        Inches(left),
        Inches(top),
        Inches(width),
        Inches(height),
    )
    arr.fill.solid()
    arr.fill.fore_color.rgb = CARD_BG
    arr.line.color.rgb = color
    arr.line.width = Pt(1.25)
    tf = arr.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.text = label
    p.font.size = Pt(9.5)
    p.font.bold = True
    p.font.color.rgb = color
    p.alignment = PP_ALIGN.CENTER


def generate_pipeline_demo_images() -> dict[str, io.BytesIO]:
    h, w = 360, 480
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)

    cx1, cy1 = w * 0.35, h * 0.45
    r1 = np.sqrt((xx - cx1) ** 2 + (yy - cy1) ** 2)
    ring1 = np.exp(-((r1 - 72.0) ** 2) / (2.0 * 9.0**2))
    core1 = np.exp(-(r1**2) / (2.0 * 38.0**2))

    cx2, cy2 = w * 0.70, h * 0.58
    r2 = np.sqrt((xx - cx2) ** 2 + (yy - cy2) ** 2)
    ring2 = np.exp(-((r2 - 50.0) ** 2) / (2.0 * 7.0**2))

    bg_grad = 0.25 * (xx / w) + 0.15 * (yy / h)
    rng = np.random.default_rng(42)
    noise = rng.normal(0, 0.035, (h, w)).astype(np.float32)

    red = np.clip((bg_grad + 0.75 * ring1 + 0.45 * core1 + 0.70 * ring2 + noise) * 255, 0, 255).astype(np.uint8)
    green = np.clip((0.20 * (1 - xx / w) + 0.55 * core1 + 0.30 * ring2 + noise) * 255, 0, 255).astype(np.uint8)
    blue = np.clip((0.30 * (yy / h) + 0.25 * ring1 + 0.65 * ring2 + noise) * 255, 0, 255).astype(np.uint8)

    cv2.rectangle(red, (28, 28), (110, 44), 235, -1)
    cv2.rectangle(green, (28, 28), (110, 44), 90, -1)
    cv2.rectangle(blue, (28, 28), (110, 44), 60, -1)

    orig_bgr = np.stack([blue, green, red], axis=-1)
    zeros = np.zeros_like(red)
    red_tinted_bgr = np.stack([zeros, zeros, red], axis=-1)

    sep = np.full((h, 8, 3), (30, 41, 59), dtype=np.uint8)
    side_by_side = np.hstack([orig_bgr, sep, red_tinted_bgr])

    blurred_red = cv2.GaussianBlur(red, (5, 5), 1.2)
    med_val = float(np.median(blurred_red))
    canny_low = int(max(10, 0.66 * med_val))
    canny_high = int(min(255, max(canny_low + 20, 1.33 * med_val)))
    edges_binary = cv2.Canny(blurred_red, canny_low, canny_high)

    sobel_x = cv2.Sobel(blurred_red, cv2.CV_32F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(blurred_red, cv2.CV_32F, 0, 1, ksize=3)
    grad_mag = cv2.magnitude(sobel_x, sobel_y)
    grad_norm = cv2.normalize(grad_mag, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

    edge_overlay_bgr = np.stack([edges_binary, edges_binary, red], axis=-1)
    edges_bgr = cv2.cvtColor(edges_binary, cv2.COLOR_GRAY2BGR)
    grad_bgr = cv2.cvtColor(grad_norm, cv2.COLOR_GRAY2BGR)
    edge_triptych = np.hstack([edges_bgr, sep, grad_bgr, sep, edge_overlay_bgr])

    hist_w, hist_h = 840, 320
    hist_img = np.full((hist_h, hist_w, 3), (42, 23, 15), dtype=np.uint8)
    pad_l, pad_r, pad_t, pad_b = 54, 24, 28, 42
    pw = hist_w - pad_l - pad_r
    ph = hist_h - pad_t - pad_b

    total_px = float(red.size)
    pct_r = (np.bincount(red.ravel(), minlength=256)[:256] / total_px) * 100.0
    pct_g = (np.bincount(green.ravel(), minlength=256)[:256] / total_px) * 100.0
    pct_b = (np.bincount(blue.ravel(), minlength=256)[:256] / total_px) * 100.0
    max_pct = max(float(pct_r.max()), float(pct_g.max()), float(pct_b.max()), 0.1)

    def to_pt(idx, val):
        x = int(pad_l + (idx / 255.0) * pw)
        y = int(pad_t + ph - min(val / max_pct, 1.0) * ph)
        return (x, y)

    for v in (0, 64, 128, 192, 255):
        xg = int(pad_l + (v / 255.0) * pw)
        cv2.line(hist_img, (xg, pad_t), (xg, pad_t + ph), (85, 65, 51), 1)
        cv2.putText(
            hist_img, str(v), (xg - 12, hist_h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (184, 163, 148), 1, cv2.LINE_AA
        )

    pts_g = np.array([to_pt(i, pct_g[i]) for i in range(256)], dtype=np.int32)
    pts_b = np.array([to_pt(i, pct_b[i]) for i in range(256)], dtype=np.int32)
    pts_r = np.array([to_pt(i, pct_r[i]) for i in range(256)], dtype=np.int32)

    cv2.polylines(hist_img, [pts_g], False, (94, 197, 34), 1, cv2.LINE_AA)
    cv2.polylines(hist_img, [pts_b], False, (246, 130, 59), 1, cv2.LINE_AA)

    poly_r = np.vstack([[pad_l, pad_t + ph], pts_r, [pad_l + pw, pad_t + ph]]).astype(np.int32)
    overlay = hist_img.copy()
    cv2.fillPoly(overlay, [poly_r], (68, 68, 239))
    cv2.addWeighted(overlay, 0.35, hist_img, 0.65, 0, hist_img)
    cv2.polylines(hist_img, [pts_r], False, (68, 68, 239), 2, cv2.LINE_AA)

    p50 = float(np.median(red))
    x_med = int(pad_l + (p50 / 255.0) * pw)
    cv2.line(hist_img, (x_med, pad_t), (x_med, pad_t + ph), (21, 204, 250), 2)
    cv2.putText(
        hist_img,
        f"median={p50:.0f}",
        (x_med + 8, pad_t + 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (21, 204, 250),
        1,
        cv2.LINE_AA,
    )
    cv2.rectangle(hist_img, (pad_l, pad_t), (pad_l + pw, pad_t + ph), (105, 85, 71), 1)

    def to_png_stream(img):
        _, buf = cv2.imencode(".png", img)
        bio = io.BytesIO(buf.tobytes())
        bio.seek(0)
        return bio

    return {
        "side_by_side": to_png_stream(side_by_side),
        "edge_triptych": to_png_stream(edge_triptych),
        "histogram": to_png_stream(hist_img),
    }


def build_deck(output_path: Path):
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    images = generate_pipeline_demo_images()

    # =========================================================================
    # SLIDE 1 (from sf_marimo_slide_deck.md): END-TO-END ARCHITECTURE
    # =========================================================================
    s1 = prs.slides.add_slide(blank_layout)
    set_slide_background(s1)
    add_header(
        s1,
        "Slide 1: End-to-End Architecture",
        "Real-Time Instrument Streaming with ScopeFoundry, Marimo & Live LLM Pairing",
        badge_text="sf_marimo_slide_deck.md · Slide 1",
    )

    # Subgraph 1: ScopeFoundry App (main.py)
    add_box(
        s1,
        0.55,
        1.45,
        3.2,
        2.95,
        "ScopeFoundry App (main.py)",
        [],
        bg_color=CARD_BG,
        border_color=ACCENT_BLUE,
        title_size=13,
    )
    add_box(
        s1,
        0.75,
        1.95,
        2.8,
        0.95,
        "WebcamZmqHW (OpenCV)",
        ["threaded_update() capture", "send_multipart(NOBLOCK, copy=False)"],
        bg_color=NODE_BG,
        border_color=ACCENT_BLUE,
        title_size=11,
        body_size=9.5,
    )
    add_box(
        s1,
        0.75,
        3.15,
        2.8,
        0.95,
        "WebcamLiveMeasure (PyQtGraph)",
        ["via get_latest_frame()", "Live GUI + snap_h5()"],
        bg_color=NODE_BG,
        border_color=ACCENT_TEAL,
        title_size=11,
        body_size=9.5,
    )

    # Arrow SF -> ZMQ
    add_arrow_banner(s1, 3.82, 2.15, 0.85, 0.55, "ZMQ PUB", ACCENT_GOLD)

    # Subgraph 2: ZeroMQ Transport
    add_box(
        s1,
        4.75,
        1.75,
        3.1,
        1.45,
        "ZeroMQ Transport\n(tcp://127.0.0.1:5556)",
        [
            "Multipart PUB:",
            "[topic, meta_json, ndarray_bytes]",
        ],
        bg_color=CARD_BG,
        border_color=ACCENT_GOLD,
        title_size=12,
        body_size=10.5,
    )

    # Arrow ZMQ -> MARIMO
    add_arrow_banner(s1, 7.92, 2.15, 0.95, 0.55, "recv_latest", ACCENT_GOLD)

    # Subgraph 3: Live Marimo Kernel
    add_box(
        s1,
        8.95,
        1.45,
        3.8,
        4.2,
        "Live Marimo Kernel\n(red_channel_viewer.py :2719)",
        [],
        bg_color=CARD_BG,
        border_color=ACCENT_RED,
        title_size=13,
    )
    add_box(
        s1,
        9.15,
        2.15,
        3.4,
        0.70,
        "Cell vblA: zmq.SUB (rcvhwm=60)",
        ["Drains queue → newest frame"],
        bg_color=NODE_BG,
        border_color=ACCENT_GOLD,
        title_size=10.5,
        body_size=9,
    )
    add_box(
        s1,
        9.15,
        2.98,
        3.4,
        0.70,
        "Cell bkHC: Red Channel + Base64 JPEG",
        ["Extracts red_channel & frame_cache"],
        bg_color=NODE_BG,
        border_color=ACCENT_RED,
        title_size=10.5,
        body_size=9,
    )
    add_box(
        s1,
        9.15,
        3.81,
        3.4,
        0.75,
        "Cell fXKi: Canny & Sobel Edges",
        ["GaussianBlur + Canny + Sobel + Cyan overlay"],
        bg_color=NODE_BG,
        border_color=ACCENT_TEAL,
        title_size=10.5,
        body_size=9,
    )
    add_box(
        s1,
        9.15,
        4.68,
        3.4,
        0.75,
        "Cell dblj: 256-Bin SVG Histogram",
        ["np.bincount + P10/P50/P90 + G/B curves"],
        bg_color=NODE_BG,
        border_color=ACCENT_BLUE,
        title_size=10.5,
        body_size=9,
    )

    # Subgraph 4: LLM Agent (marimo-pair Skill)
    add_box(
        s1,
        3.95,
        3.70,
        3.75,
        1.95,
        "LLM Agent (marimo-pair Skill)",
        [
            "• execute-code.sh → marimo._code_mode",
            "• AsyncCodeModeContext (cm.get_context())",
            "• Inspects & mutates live DAG + auto-saves .py",
        ],
        bg_color=CARD_BG,
        border_color=ACCENT_PURPLE,
        title_size=12.5,
        body_size=10,
    )
    add_arrow_banner(
        s1,
        7.78,
        4.35,
        1.10,
        0.55,
        "Live DAG",
        ACCENT_PURPLE,
        shape_type=MSO_SHAPE.LEFT_RIGHT_ARROW,
    )

    # Bottom takeaway bullets from Slide 1
    add_box(
        s1,
        0.55,
        5.82,
        12.2,
        1.35,
        "Key Architectural Takeaways",
        [
            "• Decoupled Acquisition & Analysis: WebcamStreamApp (main.py) handles hardware control and local HDF5 snapshots, while red_channel_viewer.py subscribes to the live stream without blocking the camera thread.",
            "• Hot-Swappable Visualizations: The LLM connects directly to the active Marimo kernel via marimo-pair (SKILL.md) to add and refine analysis cells while frames are streaming.",
        ],
        bg_color=CARD_BG,
        border_color=BORDER_CLR,
        title_color=ACCENT_BLUE,
        title_size=13,
        body_size=11,
    )

    # =========================================================================
    # SLIDE 2 (from sf_marimo_slide_deck.md): SCOPEFOUNDRY DATA STREAMING
    # =========================================================================
    s2 = prs.slides.add_slide(blank_layout)
    set_slide_background(s2)
    add_header(
        s2,
        "Slide 2: ScopeFoundry Data Streaming (WebcamZmqHW)",
        "HardwareComponent background capture thread + zero-copy ZMQ PUB + PyQtGraph live viewer",
        badge_text="sf_marimo_slide_deck.md · Slide 2",
    )

    add_box(
        s2,
        0.55,
        1.45,
        7.1,
        3.65,
        "Hardware Component (webcam_zmq_hw.py — WebcamZmqHW)",
        [
            "• Subclasses ScopeFoundry.HardwareComponent:",
            "  - setup(): Defines LoggedQuantity settings (camera_index, width, height, fps_target, fps_measured, color_mode, zmq_bind_address, zmq_topic, zmq_hwm=60, stream_enabled, frame_count).",
            "  - connect(): Opens cv2.VideoCapture and binds a zmq.PUB socket (tcp://*:5556, SNDHWM=60, LINGER=0).",
            "  - threaded_update(): Automatically runs in ScopeFoundry's background hardware thread while connected; captures frames, converts color (RGB/BGR/GRAY), updates smoothed FPS, and publishes a 3-part zero-copy ZMQ message.",
        ],
        bg_color=CARD_BG,
        border_color=ACCENT_BLUE,
        title_size=14,
        body_size=11.5,
    )

    add_box(
        s2,
        7.85,
        1.45,
        4.9,
        3.65,
        "In-App Live Viewer (webcam_live_measure.py)",
        [
            "• WebcamLiveMeasure subclasses ScopeFoundry.Measurement",
            "• Displays live camera feed in PyQtGraph (ImageItem + HistogramLUTItem) with row-major axis ordering",
            "• Embeds WebcamZmqHW control widgets alongside the live viewport",
            "• Includes snap_h5 operation and save_h5_on_stop setting for archiving snapshots to HDF5 via ScopeFoundry h5_io",
        ],
        bg_color=CARD_BG,
        border_color=ACCENT_TEAL,
        title_size=14,
        body_size=11.5,
    )

    add_code_box(
        s2,
        0.55,
        5.30,
        12.2,
        1.85,
        "Zero-Copy Multipart ZMQ Publish in WebcamZmqHW.threaded_update()",
        """self.pub_socket.send_multipart(
    [topic_bytes, json.dumps(meta).encode("utf-8"), frame],
    flags=zmq.NOBLOCK,
    copy=False,
)""",
        font_size=12,
    )

    # =========================================================================
    # SLIDE 3 (from sf_marimo_slide_deck.md): MARIMO NOTEBOOK RECEIVING DATA
    # =========================================================================
    s3 = prs.slides.add_slide(blank_layout)
    set_slide_background(s3)
    add_header(
        s3,
        "Slide 3: Marimo Notebook Receiving Data (red_channel_viewer.py)",
        "Reactive Dataflow DAG & engineering flicker-free, zero-lag live streaming in Marimo",
        badge_text="sf_marimo_slide_deck.md · Slide 3",
    )

    add_box(
        s3,
        0.55,
        1.45,
        5.9,
        5.65,
        "Reactive Dataflow DAG",
        [
            "1. Imports (Hbol):",
            "   Loads base64, cv2, marimo, numpy, and zmq_sub_client.py.",
            "",
            "2. UI Controls (MJUe):",
            "   Defines address_input, topic_input, display_mode, and refresh = mo.ui.refresh(options=['0.2s', '0.5s', '1s', '2s', '5s'], default_interval='0.5s').",
            "",
            "3. Persistent Socket & Cache (vblA):",
            "   Creates sub_socket (create_sub_socket) and frame_cache = {'latest': None}. Only re-runs if the address or topic changes.",
            "",
            "4. Frame Polling & Red Channel View (bkHC):",
            "   Triggered by refresh.value; calls recv_latest_frame(), extracts red_channel, and exposes (frame, red_channel, meta, to_data_url) to downstream cells.",
        ],
        bg_color=CARD_BG,
        border_color=ACCENT_BLUE,
        title_size=15,
        body_size=11.5,
    )

    add_box(
        s3,
        6.70,
        1.45,
        6.05,
        2.70,
        "Engineering Smooth Live Streaming: Eliminating Flicker",
        [
            "• Virtual File HTTP Round-Trip:",
            "  Passing raw bytes to mo.image() creates a new /@file/... virtual URL on every tick, causing a secondary browser HTTP request and momentary blank frame.",
            "• Solution:",
            "  Encoding frames as inline data:image/jpeg;base64,... strings and caching frame_cache['latest'] across ticks eliminates both HTTP round-trip flicker and empty-poll warning flashes.",
        ],
        bg_color=CARD_BG,
        border_color=ACCENT_RED,
        title_size=14,
        body_size=11,
    )

    add_box(
        s3,
        6.70,
        4.40,
        6.05,
        2.70,
        "Engineering Smooth Live Streaming: Eliminating ZMQ Lag",
        [
            "• ZeroMQ Tail-Drop Behavior:",
            "  ZeroMQ PUB/SUB high-water marks (HWM) use tail-drop (dropping new messages once the queue fills with old ones).",
            "• Solution:",
            "  Setting rcvhwm=60 and draining all queued raw multipart buffers with recv_multipart(flags=zmq.NOBLOCK, copy=False) before decoding only the final message guarantees every 0.5s refresh renders the newest camera frame.",
        ],
        bg_color=CARD_BG,
        border_color=ACCENT_TEAL,
        title_size=14,
        body_size=11,
    )

    # =========================================================================
    # SLIDE 4 (from sf_marimo_slide_deck.md): LLM CONNECTION VIA MARIMO-PAIR
    # =========================================================================
    s4 = prs.slides.add_slide(blank_layout)
    set_slide_background(s4)
    add_header(
        s4,
        "Slide 4: LLM Connection to Marimo via marimo-pair Skill",
        "Sequence of scratchpad & marimo._code_mode interactions across Browser UI, Agent, Kernel, and Disk",
        badge_text="sf_marimo_slide_deck.md · Slide 4",
    )

    # 5 Participant Headers across top
    actors = [
        ("User\n(Browser UI :2719)", ACCENT_BLUE),
        ("LLM Agent\n(marimo-pair)", ACCENT_PURPLE),
        ("Script\n(execute-code.sh)", ACCENT_GOLD),
        ("Marimo Kernel\n(_code_mode)", ACCENT_RED),
        ("Disk Artifact\n(red_channel_viewer.py)", ACCENT_TEAL),
    ]
    for idx, (label, clr) in enumerate(actors):
        x_left = 0.55 + idx * 2.50
        add_box(
            s4,
            x_left,
            1.40,
            2.25,
            0.72,
            label,
            [],
            bg_color=CARD_BG,
            border_color=clr,
            title_size=11,
            align=PP_ALIGN.CENTER,
        )

    # Sequence steps box
    seq_steps = [
        "1.  Agent  ──►  execute-code.sh  ──►  Kernel (POST /api/kernel/scratchpad):   Inspect API via help(marimo._code_mode)",
        "2.  Kernel ──►  Agent:                                                         Returns AsyncCodeModeContext docs & live cell list",
        "3.  Agent  ──►  execute-code.sh  ──►  Kernel:                                  Enter async with cm.get_context() as ctx",
        "4.  Agent  ──►  Kernel:                                                        Read ctx.cells[id].code (satisfies staleness guard)",
        "5.  Agent  ──►  Kernel:                                                        Queue ctx.edit_cell(...) / ctx.create_cell(..., hide_code=False)",
        "6.  Agent  ──►  Kernel:                                                        Queue ctx.run_cell(...) for target cell & reactive descendants",
        "7.  Kernel ──►  Kernel (Internal Validation):                                  Dry-run DAG compile check (verifies no cycles or duplicate defs)",
        "8.  Kernel ──►  User (Browser UI :2719):                                       Broadcasts WebSocket NotebookDocumentTransactionNotification",
        "9.  Kernel ──►  Disk (red_channel_viewer.py):                                  Auto-formats and saves updated .py notebook file on disk",
    ]
    add_code_box(
        s4,
        0.55,
        2.28,
        12.2,
        3.40,
        "Interaction Sequence (Agent ↔ execute-code.sh ↔ Marimo Kernel ↔ Browser UI & Disk)",
        "\n".join(seq_steps),
        font_size=10.5,
    )

    # IMPORTANT Callout from Slide 4
    add_box(
        s4,
        0.55,
        5.85,
        12.2,
        1.25,
        "IMPORTANT — Active Runtime Is the Source of Truth",
        [
            "During a live `marimo edit` session, editing the `.py` file on disk directly is ignored by the running kernel and overwritten on save.",
            "All structural and code changes must go through `marimo._code_mode` (`cm`), which updates both the live kernel DAG and the saved `.py` file.",
        ],
        bg_color=CARD_BG,
        border_color=ACCENT_GOLD,
        title_color=ACCENT_GOLD,
        title_size=13,
        body_size=11,
    )

    # =========================================================================
    # SLIDE 5 (from sf_marimo_slide_deck.md): CONVERSATIONAL PROMPTS TABLE
    # =========================================================================
    s5 = prs.slides.add_slide(blank_layout)
    set_slide_background(s5)
    add_header(
        s5,
        "Slide 5: Conversational Prompts Used to Build Live Visualizations",
        "Step-by-step progression from ScopeFoundry hardware setup to live Marimo pairing",
        badge_text="sf_marimo_slide_deck.md · Slide 5",
    )

    rows_data = [
        (
            "Stage",
            "User Prompt",
            "Agent Action & Live Result",
        ),
        (
            "1. Instrument & Stream Setup",
            '"a scopefoundry app with a hardware component that captures webcam and streams out frames using zmq pub"',
            "Clarified multipart format & live viewer tab; created webcam_zmq_hw.py, webcam_live_measure.py, zmq_sub_client.py, and main.py.",
        ),
        (
            "2. Initial Subscriber Notebook",
            '"now create a marimo notebook that subs that zmq topic and displays the red channel of the image"',
            "Created red_channel_viewer.py with persistent zmq.SUB cell, mo.ui.refresh, and Red-tinted / Grayscale / Side-by-side views.",
        ),
        (
            "3. Live Pairing & Widget Fix",
            '"ok i just added a skill for marimo-pair so you can edit notebook live" + "options.0: Must be greater than 0.1 seconds"',
            "Launched marimo edit --no-token on :2719, ran help(cm), and live-edited cell MJUe via cm.get_context() to remove '0.05s'.",
        ),
        (
            "4. Visual & Latency Tuning",
            '"why is image flickering?" & "there is some lag, can we just reduce refresh rate so less lag?"',
            "Replaced virtual file URLs with inline data:image/jpeg;base64 URIs, added frame_cache, set poll interval to 0.5s, and added fast zero-copy ZMQ queue draining.",
        ),
        (
            "5. Live Feature: Edge Detection",
            '"add an edge finding processing step to the data in a new cell"',
            "Hot-inserted cell fXKi: Gaussian blur, adaptive Canny edges, Sobel gradient magnitude, and cyan edge overlay on the red channel.",
        ),
        (
            "6. Live Feature: Stream Histogram",
            '"create a cell showing histogram of data stream"',
            "Hot-inserted cell dblj: 256-bin np.bincount pixel distribution rendered as a flicker-free inline <svg> chart with P10/Median/P90 stats and G/B reference curves.",
        ),
    ]

    table_shape = s5.shapes.add_table(
        len(rows_data), 3, Inches(0.55), Inches(1.40), Inches(12.2), Inches(5.7)
    )
    table = table_shape.table
    table.columns[0].width = Inches(2.5)
    table.columns[1].width = Inches(4.3)
    table.columns[2].width = Inches(5.4)

    for r_idx, row in enumerate(rows_data):
        for c_idx, val in enumerate(row):
            cell = table.cell(r_idx, c_idx)
            cell.fill.solid()
            if r_idx == 0:
                cell.fill.fore_color.rgb = RGBColor(51, 65, 85)
            elif r_idx % 2 == 1:
                cell.fill.fore_color.rgb = CARD_BG
            else:
                cell.fill.fore_color.rgb = CODE_BG

            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.text = val
            if r_idx == 0:
                p.font.size = Pt(11.5)
                p.font.bold = True
                p.font.color.rgb = ACCENT_BLUE
            else:
                p.font.size = Pt(10)
                p.font.bold = c_idx == 0
                p.font.color.rgb = (
                    ACCENT_GOLD
                    if c_idx == 0
                    else ( RGBColor(226, 232, 240) if c_idx == 1 else TEXT_WHITE )
                )

    # =========================================================================
    # SLIDE 6: MARIMO NOTEBOOK VISUAL OUTPUTS GALLERY (CELLS bkHC, fXKi, dblj)
    # =========================================================================
    s6 = prs.slides.add_slide(blank_layout)
    set_slide_background(s6)
    add_header(
        s6,
        "Bonus: Live Marimo Notebook Outputs (Cells bkHC, fXKi & dblj)",
        "Rendered outputs from the three visualization cells in red_channel_viewer.py",
        badge_text="Marimo Live Outputs",
    )

    s6.shapes.add_picture(
        images["side_by_side"],
        Inches(0.55),
        Inches(1.55),
        width=Inches(5.85),
    )
    add_box(
        s6,
        0.55,
        3.90,
        5.85,
        0.75,
        "Cell bkHC: Original Stream vs. Isolated Red Channel",
        ["Inline base64 JPEG data URL + frame_cache['latest']"],
        bg_color=CARD_BG,
        border_color=ACCENT_RED,
        title_size=11.5,
        body_size=10,
    )

    s6.shapes.add_picture(
        images["edge_triptych"],
        Inches(6.75),
        Inches(1.55),
        width=Inches(6.0),
    )
    add_box(
        s6,
        6.75,
        3.25,
        6.0,
        1.40,
        "Cell fXKi: Canny Edges, Sobel Gradient & Cyan-on-Red Overlay",
        [
            "GaussianBlur(5×5) → Median-adaptive Canny → Sobel 2D Magnitude → Cyan Edge Overlay",
        ],
        bg_color=CARD_BG,
        border_color=ACCENT_TEAL,
        title_size=11.5,
        body_size=10,
    )

    s6.shapes.add_picture(
        images["histogram"],
        Inches(0.55),
        Inches(4.80),
        width=Inches(5.85),
    )
    add_box(
        s6,
        6.75,
        4.80,
        6.0,
        2.25,
        "Cell dblj: Flicker-Free 256-Bin SVG Intensity Histogram",
        [
            "• Red channel pixel distribution (filled red area) + G/B reference curves",
            "• Dashed yellow vertical marker tracking live Median (P50) intensity",
            "• Live KPI stat cards for P10, Median (P50), P90, and Std Dev",
        ],
        bg_color=CARD_BG,
        border_color=ACCENT_GOLD,
        title_size=12.5,
        body_size=11,
    )

    prs.save(str(output_path))
    # Keep sf_marimo_streaming_slides.pptx in sync as well
    alt_path = output_path.parent / "sf_marimo_streaming_slides.pptx"
    if alt_path != output_path:
        shutil.copyfile(output_path, alt_path)
    print(f"Saved presentation to {output_path} ({len(prs.slides)} slides)")


if __name__ == "__main__":
    build_deck(Path(__file__).parent / "sf_marimo_slide_deck.pptx")
