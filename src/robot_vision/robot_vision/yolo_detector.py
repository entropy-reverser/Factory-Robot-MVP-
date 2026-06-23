#!/usr/bin/env python3
"""
YOLODetectorNode — ROS2 Python node for real-time object detection.

Subscribes to a color image topic, runs YOLO inference using pre-trained
weights (yolo26n.pt), and publishes detections in vision_msgs/Detection2DArray
format plus an annotated visualization image.

No training is performed; this is pure inference.
"""

import os
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy

from sensor_msgs.msg import Image
from vision_msgs.msg import Detection2DArray, Detection2D, ObjectHypothesisWithPose
from cv_bridge import CvBridge

import cv2
import numpy as np

# Ultralytics YOLO — installed via pip in the Docker image
from ultralytics import YOLO


class YOLODetectorNode(Node):
    """ROS2 node wrapping Ultralytics YOLO for factory cargo detection."""

    def __init__(self):
        super().__init__("yolo_detector")

        # ------------------------------------------------------------------
        # 1. ROS2 Parameters (configurable via YAML or CLI)
        # ------------------------------------------------------------------
        self.declare_parameter("model_path", "/workspace/weights/yolo26n.pt")
        self.declare_parameter("confidence_threshold", 0.5)
        self.declare_parameter("device", "auto")          # "cpu", "cuda", or "auto"
        self.declare_parameter("publish_visualization", True)
        self.declare_parameter("input_topic", "/camera/color/image_raw")
        self.declare_parameter("inference_rate", 10.0)      # Hz
        self.declare_parameter("image_queue_size", 2)

        self.model_path = self.get_parameter("model_path").value
        self.conf_thresh = self.get_parameter("confidence_threshold").value
        self.device = self.get_parameter("device").value
        self.publish_viz = self.get_parameter("publish_visualization").value
        self.input_topic = self.get_parameter("input_topic").value
        self.inference_rate = self.get_parameter("inference_rate").value
        self.queue_size = self.get_parameter("image_queue_size").value

        # ------------------------------------------------------------------
        # 2. YOLO Model Loading
        # ------------------------------------------------------------------
        if not os.path.isfile(self.model_path):
            self.get_logger().error(f"Model file not found: {self.model_path}")
            raise FileNotFoundError(f"Model file not found: {self.model_path}")

        self.get_logger().info(f"Loading YOLO model from: {self.model_path}")
        self.model = YOLO(self.model_path)
        # Warm-up inference on a dummy image to initialize CUDA/graphs
        dummy = np.zeros((480, 640, 3), dtype=np.uint8)
        _ = self.model.predict(dummy, verbose=False, device=self.device)
        self.get_logger().info("YOLO model warm-up complete.")

        # ------------------------------------------------------------------
        # 3. CV Bridge (ROS Image <-> OpenCV)
        # ------------------------------------------------------------------
        self.bridge = CvBridge()
        self.latest_image = None
        self.latest_header = None

        # ------------------------------------------------------------------
        # 4. QoS Profile: Best-effort for images to avoid back-pressure
        # ------------------------------------------------------------------
        qos = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=self.queue_size,
        )

        # ------------------------------------------------------------------
        # 5. Subscribers
        # ------------------------------------------------------------------
        self.image_sub = self.create_subscription(
            Image,
            self.input_topic,
            self._image_callback,
            qos,
        )

        # ------------------------------------------------------------------
        # 6. Publishers
        # ------------------------------------------------------------------
        self.detection_pub = self.create_publisher(
            Detection2DArray,
            "/vision/detections",
            10,
        )

        if self.publish_viz:
            self.viz_pub = self.create_publisher(
                Image,
                "/vision/detection_image",
                10,
            )

        # ------------------------------------------------------------------
        # 7. Inference Timer (throttled to inference_rate Hz)
        # ------------------------------------------------------------------
        timer_period = 1.0 / self.inference_rate
        self.timer = self.create_timer(timer_period, self._inference_callback)

        self.get_logger().info(
            f"YOLODetectorNode initialized. "
            f"Subscribed to {self.input_topic}, "
            f"publishing to /vision/detections at {self.inference_rate} Hz."
        )

    # ------------------------------------------------------------------
    # Image Callback: stores the latest frame (non-blocking)
    # ------------------------------------------------------------------
    def _image_callback(self, msg: Image):
        try:
            self.latest_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
            self.latest_header = msg.header
        except Exception as e:
            self.get_logger().warning(f"CV Bridge conversion failed: {e}")

    # ------------------------------------------------------------------
    # Inference Callback: runs YOLO and publishes results
    # ------------------------------------------------------------------
    def _inference_callback(self):
        if self.latest_image is None:
            return

        # Copy frame reference so we do not hold the lock during inference
        frame = self.latest_image.copy()
        header = self.latest_header

        # Run YOLO inference (returns list of Results objects)
        results = self.model.predict(
            frame,
            verbose=False,
            conf=self.conf_thresh,
            device=self.device,
        )

        if not results:
            return

        result = results[0]  # single image => single result
        boxes = result.boxes

        # Build Detection2DArray message
        det_array = Detection2DArray()
        det_array.header = header

        # Annotate visualization if enabled
        viz_frame = frame.copy() if self.publish_viz else None

        if boxes is not None:
            for box in boxes:
                cls_id = int(box.cls.item())
                cls_name = result.names.get(cls_id, f"class_{cls_id}")
                conf = float(box.conf.item())

                # Bounding box in pixel coordinates
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                cx = (x1 + x2) / 2.0
                cy = (y1 + y2) / 2.0
                w = x2 - x1
                h = y2 - y1

                # Normalize to [0, 1] for vision_msgs
                img_h, img_w = frame.shape[:2]
                norm_cx = cx / img_w
                norm_cy = cy / img_h
                norm_w = w / img_w
                norm_h = h / img_h

                # Build Detection2D
                det = Detection2D()
                det.header = header
                det.bbox.center.position.x = norm_cx
                det.bbox.center.position.y = norm_cy
                det.bbox.size_x = norm_w
                det.bbox.size_y = norm_h

                # Hypothesis (class + score)
                hyp = ObjectHypothesisWithPose()
                hyp.hypothesis.class_id = cls_name
                hyp.hypothesis.score = conf
                det.results.append(hyp)

                det_array.detections.append(det)

                # Draw on visualization frame
                if viz_frame is not None:
                    cv2.rectangle(viz_frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                    label = f"{cls_name}: {conf:.2f}"
                    cv2.putText(
                        viz_frame, label, (int(x1), int(y1) - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2,
                    )

        # Publish detection array
        self.detection_pub.publish(det_array)

        # Publish visualization image
        if viz_frame is not None:
            viz_msg = self.bridge.cv2_to_imgmsg(viz_frame, encoding="bgr8")
            viz_msg.header = header
            self.viz_pub.publish(viz_msg)

        # Optional: log summary every N frames
        self.get_logger().debug(
            f"Inference complete: {len(det_array.detections)} objects detected."
        )


def main(args=None):
    rclpy.init(args=args)
    node = YOLODetectorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Shutting down YOLODetectorNode.")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
