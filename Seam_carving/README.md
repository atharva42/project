# Seam Carving using OpenCV in C++

A content-aware image resizing project implemented using C++ and OpenCV.

## Overview

This project implements the **Seam Carving Algorithm**, which intelligently resizes images by removing low-energy seams instead of uniformly scaling the image.

Unlike traditional resizing methods, seam carving preserves important image content while reducing image dimensions.

---

# Features

- Content-aware image resizing
- Vertical seam removal
- Horizontal seam removal
- Dynamic programming based seam selection
- Energy calculation using neighboring pixel gradients
- OpenCV based image processing

---

# Technologies Used

- C++
- OpenCV

---

# Algorithm Explanation

## 1. Energy Calculation

Each pixel is assigned an energy value based on the intensity differences between neighboring pixels.

Higher energy:
- edges
- important objects
- detailed regions

Lower energy:
- smooth areas
- background regions

Energy Formula:

```text
Energy = sqrt(deltaX² + deltaY²)
```

Where:
- `deltaX` = horizontal gradient
- `deltaY` = vertical gradient

---

## 2. Dynamic Programming

The algorithm computes cumulative minimum energy for all possible seams.

### Vertical Seam

Allowed transitions:
- top-left
- top
- top-right

### Horizontal Seam

Allowed transitions:
- left-up
- left
- left-down

---

## 3. Seam Backtracking

After calculating cumulative energies:
- the seam with minimum energy is identified
- the seam path is traced back
- pixels belonging to the seam are removed

---

## 4. Image Resizing

The process repeats until the required width and height are achieved.

---

# Project Structure

```text
.
├── main.cpp
├── input.jpg
├── output.jpg
└── README.md
```

---

# Prerequisites

Install the following before running the project:

- C++ Compiler
- OpenCV Library

---

# OpenCV Installation

## Ubuntu/Debian

```bash
sudo apt update
sudo apt install libopencv-dev
```

---

# Compilation

Compile the program using:

```bash
g++ main.cpp -o seam_carving `pkg-config --cflags --libs opencv4`
```

---

# Running the Program

```bash
./seam_carving input.jpg
```

---

# Input

The program asks for:

```text
Enter the Width to be Reduced :
Enter the Height to be Reduced :
```

Example:

```text
Enter the Width to be Reduced : 200
Enter the Height to be Reduced : 100
```

---

# Output

The resized image is saved as:

```text
output.jpg
```

---

# Functions Used

| Function | Description |
|---|---|
| `energyCalculation()` | Computes pixel energy |
| `findVericalLowestEnergySeam()` | Finds minimum energy vertical seam |
| `findHorizontalLowestEnergySeam()` | Finds minimum energy horizontal seam |
| `removeVerticalSeam()` | Removes vertical seam |
| `removeHorizontalSeam()` | Removes horizontal seam |

---

# Time Complexity

Let:
- `H` = image height
- `W` = image width

### Energy Computation
```text
O(H × W)
```

### Dynamic Programming
```text
O(H × W)
```

### Seam Removal
```text
O(H + W)
```

Overall complexity depends on the number of seams removed.

---

# Sample Workflow

1. Load image
2. Compute energy map
3. Find minimum energy seam
4. Remove seam
5. Repeat until desired dimensions are reached
6. Save resized image

---

# Applications

- Intelligent image resizing
- Thumbnail generation
- Responsive web design
- Image retargeting
- Content-aware editing

---

# Notes

- The project uses wrap-around boundary conditions for edge pixels.
- Seam carving preserves important image regions better than standard resizing methods.
- Repeated seam removal may introduce artifacts for aggressive resizing.

Because eventually even the algorithm runs out of harmless pixels to sacrifice. Tiny computational tragedy happening row by row.

---