# Face Recognition using PCA (Eigenfaces)

This project implements a facial recognition system using **Principal Component Analysis (PCA)** and the **Eigenfaces** method.

The system identifies faces by projecting images into a lower-dimensional feature space and comparing facial features.

---

# Dataset

Dataset: **AT&T Face Dataset**

- 40 subjects
- 10 grayscale images per subject
- Image size: `92 × 112`

Variations include:
- lighting
- facial expressions
- glasses/no glasses

Dataset Link:  
https://git-disl.github.io/GTDLBench/datasets/att_face_dataset/

Reference Paper:  
https://sites.cs.ucsb.edu/~mturk/Papers/mturk-CVPR91.pdf

---

# Tasks Performed

- Loaded and split dataset into training and test sets
- Implemented PCA from scratch
- Generated Eigenfaces
- Reconstructed images using different numbers of principal components
- Visualized mean face and Eigenfaces
- Performed face recognition using Euclidean distance
- Evaluated accuracy for different PCA dimensions

---

# Technologies Used

- Python
- NumPy
- OpenCV
- Matplotlib

---

# Recognition Pipeline

1. Convert images into vectors
2. Compute mean face
3. Apply PCA
4. Project images into Eigenface space
5. Compare feature vectors using Euclidean distance
6. Predict closest match

---

# Results

- PCA reduced dimensionality effectively
- Higher principal components improved reconstruction quality
- Eigenfaces captured important facial features
- Good recognition accuracy achieved with fewer dimensions

---

# Author

Atharva Pande