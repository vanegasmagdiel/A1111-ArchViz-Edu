# OpenCV metadata shims

A1111 + ControlNet pulls three PyPI projects that all ship the same `cv2` namespace. v8.1 keeps **only `opencv-contrib-python==4.10.0.84` as the binary provider**. The two tiny local wheels in this folder contain metadata only and declare a dependency on that provider. They satisfy the package-name requirements of ControlNet (`opencv-python`) and Albumentations (`opencv-python-headless`) without installing overlapping `cv2` binaries.

The runtime gate verifies that both shim distributions contain zero `cv2` files and that `opencv-contrib-python` owns the actual `cv2` files. These wheels are local ArchViz artifacts, not official OpenCV wheels.
