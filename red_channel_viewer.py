import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import base64
    import cv2
    import marimo as mo
    import numpy as np

    from zmq_sub_client import create_sub_socket, recv_latest_frame


    return base64, create_sub_socket, cv2, mo, np, recv_latest_frame


@app.cell(hide_code=True)
def _(mo):
    address_input = mo.ui.text(
        value="tcp://127.0.0.1:5556",
        label="ZMQ PUB Address",
    )
    topic_input = mo.ui.text(
        value="frame",
        label="Topic",
    )
    display_mode = mo.ui.dropdown(
        options=[
            "Red-tinted (R, 0, 0)",
            "Grayscale intensity",
            "Side-by-side (Original + Red)",
        ],
        value="Red-tinted (R, 0, 0)",
        label="Red Channel View",
    )
    refresh = mo.ui.refresh(
        options=["0.2s", "0.5s", "1s", "2s", "5s"],
        default_interval="0.5s",
        label="Poll Interval",
    )

    mo.vstack(
        [
            mo.md("## ScopeFoundry Webcam ZMQ Stream — Red Channel Viewer"),
            mo.hstack(
                [address_input, topic_input, display_mode, refresh],
                justify="start",
                gap=1.5,
            ),
        ]
    )
    return address_input, display_mode, refresh, topic_input


@app.cell(hide_code=True)
def _(address_input, create_sub_socket, topic_input):
    sub_socket = create_sub_socket(
        connect_address=address_input.value.strip(),
        topic=topic_input.value.strip(),
        rcvhwm=60,
    )
    frame_cache = {"latest": None}

    return frame_cache, sub_socket


@app.cell(hide_code=True)
def _(
    base64,
    cv2,
    display_mode,
    frame_cache,
    mo,
    np,
    recv_latest_frame,
    refresh,
    sub_socket,
):
    # Reference refresh.value so this cell re-executes on every timer tick
    _ = refresh.value

    def to_data_url(img_bgr_or_gray):
        _, buf = cv2.imencode(".jpg", img_bgr_or_gray, [cv2.IMWRITE_JPEG_QUALITY, 85])
        b64 = base64.b64encode(buf).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"

    new_result = recv_latest_frame(sub_socket, timeout_ms=30)
    if new_result is not None:
        frame_cache["latest"] = new_result

    result = frame_cache["latest"]

    if result is None:
        frame = None
        red_channel = None
        meta = None
        output = mo.callout(
            mo.md(
                "Waiting for frames on ZMQ SUB socket... "
                "Make sure the ScopeFoundry app (`uv run python main.py`) is running "
                "and `webcam_zmq` hardware is **connected** with `stream_enabled = True`."
            ),
            kind="warn",
        )
    else:
        topic, meta, frame = result
        color_mode = meta.get("color_mode", "RGB")

        # Extract the Red channel based on upstream color format
        if frame.ndim == 3 and frame.shape[2] >= 3:
            if color_mode == "BGR":
                red_channel = frame[:, :, 2]
                orig_bgr = frame
            else:
                # Default RGB
                red_channel = frame[:, :, 0]
                orig_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        else:
            # Grayscale fallback
            red_channel = frame
            orig_bgr = frame

        # Build an OpenCV BGR array representing the red-tinted image: (B=0, G=0, R=red)
        zeros = np.zeros_like(red_channel)
        red_tinted_bgr = np.stack([zeros, zeros, red_channel], axis=-1)

        if display_mode.value == "Grayscale intensity":
            view_widget = mo.image(
                src=to_data_url(red_channel),
                caption=f"Red Channel (Grayscale) — Frame #{meta['frame_id']}",
                width=640,
            )
        elif display_mode.value == "Side-by-side (Original + Red)":
            view_widget = mo.hstack(
                [
                    mo.image(
                        src=to_data_url(orig_bgr),
                        caption=f"Original ({color_mode}) — Frame #{meta['frame_id']}",
                        width=440,
                    ),
                    mo.image(
                        src=to_data_url(red_tinted_bgr),
                        caption=f"Red Channel — Frame #{meta['frame_id']}",
                        width=440,
                    ),
                ],
                justify="start",
                gap=1.0,
            )
        else:
            view_widget = mo.image(
                src=to_data_url(red_tinted_bgr),
                caption=f"Red Channel — Frame #{meta['frame_id']}",
                width=640,
            )

        stats_bar = mo.hstack(
            [
                mo.stat(label="Frame ID", value=str(meta["frame_id"])),
                mo.stat(
                    label="Resolution",
                    value=f"{red_channel.shape[1]}×{red_channel.shape[0]}",
                ),
                mo.stat(label="Red Mean", value=f"{red_channel.mean():.1f}"),
                mo.stat(
                    label="Red Min / Max",
                    value=f"{int(red_channel.min())} / {int(red_channel.max())}",
                ),
            ],
            justify="start",
            gap=1.5,
        )

        output = mo.vstack([stats_bar, view_widget])

    output

    return frame, meta, red_channel, to_data_url


@app.cell(hide_code=True)
def _(cv2, meta, mo, np, red_channel, to_data_url):
    if red_channel is None:
        edge_output = mo.md("_Edge detection waiting for first frame..._")
    else:
        # Smooth noise in the red channel before edge finding
        blurred_red = cv2.GaussianBlur(red_channel, (5, 5), 1.2)

        # Automatic Canny thresholds based on median red-channel intensity
        med_val = float(np.median(blurred_red))
        canny_low = int(max(10, 0.66 * med_val))
        canny_high = int(min(255, max(canny_low + 20, 1.33 * med_val)))
        edges_binary = cv2.Canny(blurred_red, canny_low, canny_high)

        # Sobel gradient magnitude for continuous edge strength
        sobel_x = cv2.Sobel(blurred_red, cv2.CV_32F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(blurred_red, cv2.CV_32F, 0, 1, ksize=3)
        grad_mag = cv2.magnitude(sobel_x, sobel_y)
        grad_norm = cv2.normalize(grad_mag, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

        # Overlay detected Canny edges (in cyan: B=255, G=255, R=0) onto the red-tinted image
        edge_overlay_bgr = np.stack(
            [edges_binary, edges_binary, red_channel],
            axis=-1,
        )

        edge_density_pct = 100.0 * float(np.count_nonzero(edges_binary)) / edges_binary.size

        edge_stats = mo.hstack(
            [
                mo.stat(label="Edge Pixels", value=f"{edge_density_pct:.2f}%"),
                mo.stat(label="Canny Thresholds", value=f"{canny_low} / {canny_high}"),
                mo.stat(label="Mean Gradient", value=f"{grad_mag.mean():.1f}"),
            ],
            justify="start",
            gap=1.5,
        )

        edge_views = mo.hstack(
            [
                mo.image(
                    src=to_data_url(edges_binary),
                    caption=f"Canny Edges — Frame #{meta['frame_id']}",
                    width=310,
                ),
                mo.image(
                    src=to_data_url(grad_norm),
                    caption=f"Sobel Gradient Magnitude — Frame #{meta['frame_id']}",
                    width=310,
                ),
                mo.image(
                    src=to_data_url(edge_overlay_bgr),
                    caption=f"Edges Overlaid on Red Channel — Frame #{meta['frame_id']}",
                    width=310,
                ),
            ],
            justify="start",
            gap=1.0,
        )

        edge_output = mo.vstack(
            [
                mo.md("### Edge Detection on Red Channel"),
                edge_stats,
                edge_views,
            ]
        )

    edge_output

    return


@app.cell(hide_code=True)
def _(frame, meta, mo, np, red_channel):
    if red_channel is None:
        hist_output = mo.md("_Histogram waiting for first frame..._")
    else:
        # Fast 256-bin intensity histogram (0..255) for the red channel
        counts_r = np.bincount(red_channel.ravel(), minlength=256)[:256].astype(np.float64)
        total_px = float(red_channel.size)
        pct_r = (counts_r / max(total_px, 1.0)) * 100.0
        max_pct = max(float(pct_r.max()), 0.1)

        p10, p50, p90 = np.percentile(red_channel, [10, 50, 90])

        # Build a crisp inline SVG area + bar chart (zero-flicker DOM update)
        svg_w, svg_h = 680, 200
        pad_l, pad_r, pad_t, pad_b = 44, 16, 16, 28
        plot_w = svg_w - pad_l - pad_r
        plot_h = svg_h - pad_t - pad_b

        def _x(bin_idx):
            return pad_l + (bin_idx / 255.0) * plot_w

        def _y(val_pct):
            return pad_t + plot_h - min(val_pct / max_pct, 1.0) * plot_h

        pts = " ".join(f"{_x(i):.1f},{_y(pct_r[i]):.1f}" for i in range(256))
        area_pts = f"{_x(0):.1f},{pad_t + plot_h:.1f} {pts} {_x(255):.1f},{pad_t + plot_h:.1f}"

        # Optional G/B channel polylines if 3-channel frame is available
        extra_lines = ""
        if frame is not None and frame.ndim == 3 and frame.shape[2] >= 3:
            c_mode = meta.get("color_mode", "RGB")
            g_ch = frame[:, :, 1]
            b_ch = frame[:, :, 0] if c_mode == "BGR" else frame[:, :, 2]
            pct_g = (np.bincount(g_ch.ravel(), minlength=256)[:256] / total_px) * 100.0
            pct_b = (np.bincount(b_ch.ravel(), minlength=256)[:256] / total_px) * 100.0
            pts_g = " ".join(f"{_x(i):.1f},{_y(pct_g[i]):.1f}" for i in range(256))
            pts_b = " ".join(f"{_x(i):.1f},{_y(pct_b[i]):.1f}" for i in range(256))
            extra_lines = (
                f'<polyline fill="none" stroke="#22c55e" stroke-width="1.2" stroke-opacity="0.55" points="{pts_g}" />'
                f'<polyline fill="none" stroke="#3b82f6" stroke-width="1.2" stroke-opacity="0.55" points="{pts_b}" />'
            )

        # X-axis ticks (0, 64, 128, 192, 255)
        x_ticks = "".join(
            f'<line x1="{_x(v):.1f}" y1="{pad_t}" x2="{_x(v):.1f}" y2="{pad_t + plot_h}" stroke="#334155" stroke-dasharray="3,3" stroke-width="0.7" />'
            f'<text x="{_x(v):.1f}" y="{svg_h - 8}" fill="#94a3b8" font-size="11" text-anchor="middle" font-family="monospace">{v}</text>'
            for v in (0, 64, 128, 192, 255)
        )

        # Median marker line
        x_med = _x(float(p50))
        med_marker = (
            f'<line x1="{x_med:.1f}" y1="{pad_t}" x2="{x_med:.1f}" y2="{pad_t + plot_h}" stroke="#facc15" stroke-width="1.5" stroke-dasharray="4,2" />'
            f'<text x="{x_med + 5:.1f}" y="{pad_t + 12}" fill="#facc15" font-size="11" font-family="monospace">median={p50:.0f}</text>'
        )

        svg_html = f"""
        <svg width="{svg_w}" height="{svg_h}" viewBox="0 0 {svg_w} {svg_h}" style="background:#0f172a; border-radius:8px; border:1px solid #1e293b;">
            {x_ticks}
            <text x="{pad_l - 6}" y="{pad_t + 10}" fill="#94a3b8" font-size="10" text-anchor="end" font-family="monospace">{max_pct:.1f}%</text>
            <text x="{pad_l - 6}" y="{pad_t + plot_h}" fill="#94a3b8" font-size="10" text-anchor="end" font-family="monospace">0%</text>
            {extra_lines}
            <polygon fill="#ef4444" fill-opacity="0.32" points="{area_pts}" />
            <polyline fill="none" stroke="#ef4444" stroke-width="2.0" points="{pts}" />
            {med_marker}
            <rect x="{pad_l}" y="{pad_t}" width="{plot_w}" height="{plot_h}" fill="none" stroke="#475569" stroke-width="1" />
        </svg>
        """

        hist_stats = mo.hstack(
            [
                mo.stat(label="P10 Intensity", value=f"{p10:.0f}"),
                mo.stat(label="Median (P50)", value=f"{p50:.0f}"),
                mo.stat(label="P90 Intensity", value=f"{p90:.0f}"),
                mo.stat(label="Std Dev", value=f"{red_channel.std():.1f}"),
            ],
            justify="start",
            gap=1.5,
        )

        hist_output = mo.vstack(
            [
                mo.md("### Live Pixel Intensity Histogram (Red Channel + G/B Reference)"),
                hist_stats,
                mo.Html(svg_html),
            ]
        )

    hist_output

    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
