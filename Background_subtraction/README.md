# Background Subtraction using Gaussian Mixture Models (GMM)

## Overview

This project implements background subtraction for video frames using **Gaussian Mixture Models (GMMs)**. The task is to extract the background from a set of training frames and then use this background to identify and subtract the foreground in test frames. This technique is useful for various computer vision applications, such as traffic monitoring, surveillance systems, and object detection.

### Methods Used:
1. **Frame Averaging**: A simple method to generate a background image by averaging all training frames.
2. **GMM Per Pixel**: For each pixel, a Gaussian Mixture Model is trained with multiple components, and the background is identified by the Gaussian component with the higher weight.

The main goal of this project is to compare the results of these methods and display the foreground extracted from test frames.

## Dependencies

To run this code, the following Python libraries are required:
- `numpy`
- `matplotlib`
- `opencv-python` (cv2)
- `scikit-learn`
- `google.colab` (for Google Colab integration)

Make sure you install these libraries by running:

```bash
pip install numpy matplotlib opencv-python scikit-learn
python3 2023201065_a2_q2.py
