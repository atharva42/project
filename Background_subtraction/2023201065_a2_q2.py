# -*- coding: utf-8 -*-
"""2023201065_A2_Q2.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1hrzSeJB-2SFNgGAHV7NccRSJAJ0R-JPj

# SMAI Assignment - 2

## Question 2: Gaussian Mixture Models

Resources:
- https://youtu.be/qMTuMa86NzU
- https://youtu.be/ZBLyXgjBx3Q

Reference: https://scikit-learn.org/stable/modules/mixture.html
"""

from google.colab import drive
drive.mount('/content/drive', force_remount=True)

# Commented out IPython magic to ensure Python compatibility.
import os
from sklearn.mixture import GaussianMixture
import numpy as np
import matplotlib.pyplot as plt
# %matplotlib inline

import cv2

"""### Part 1: Gaussian Mixture Models

We'll attempt to solve the task of background subtraction using Gaussian Mixture Models. Before that, you will need to implement the Gaussian Mixture Model algorithm from scratch.

Some details:
- Try to implement GMMs using Multi-variate Gaussian Distributions, the following tasks in the assignment are possible to implement using the Univariate version too but it might be bit inaccurate as explained below.
    - To clarify further, we could treat each pixel in our RGB image as our data point with [R, G, B] channels as the dimensions to the Multi-variate data point, and we would easily get predictions for each pixel location using Multi-variate approach.
    - Or, we could treat every single value in the given RGB image as a data point independent of what channel the belong to and consider them as Uni-variate data point, and get prediction using the Uni-variate approach.
    But this affects our prediction, since we can't simply make per pixel predtions anymore, because for every pixel location we would now have 3 different predictions.
    - To get around this, you could convert your image to Grayscale and then we would only have one channel/value corresponding to each pixel location, which would now allow us to use the Uni-variate approach for prediction, but this also means loss in information which would affect our quality of predictions.
    - Try to have a class based implementation of GMM, this would really help you in Background Subtraction task. You can get some general ideas on how to structure your class by looking at `sklearn.mixture.GaussianMixture` documentation and source code.
- The following code cell has a rough template to get you started with the implementation. You are free to change the structure of the code, this is just a suggestion to help you get started.


TLDR: You may implement the univariate version of GMMs, but it might not be as accurate as the multivariate version and it is recommended to try and implement the multivariate version.
"""

import numpy as np

class GMM(object):
    def __init__(self, n_components=1, tol=1e-3, max_iter=200, reg_covar=1e-6):
        """
        n_components: The number of mixture components.
        tol: The convergence threshold.
        max_iter: The maximum number of iterations.
        reg_covar: The regularization term added to covariance matrices for numerical stability.
        """
        self.n_components = n_components
        self.tol = tol
        self.max_iter = max_iter
        self.reg_covar = reg_covar
        self.weights = None
        self.means = None
        self.covars = None

    def _multivariate_normal_pdf(self, X, mean, covar):
        """
        Calculate the multivariate normal probability density function.
        """
        d = X.shape[1]
        det_covar = np.linalg.det(covar)
        if det_covar == 0:
            det_covar = self.reg_covar  # Regularization for numerical stability
        inv_covar = np.linalg.inv(covar + self.reg_covar * np.eye(d))  # Regularization term added to prevent |Det|=0
        constant = 1 / np.sqrt((2 * np.pi) ** d * det_covar)
        exponent = -0.5 * np.sum(np.dot((X - mean), inv_covar) * (X - mean), axis=1)
        return constant * np.exp(exponent)

    def initialize_params(self, X):
        """
        X : A collection of `N` training data points, each with dimension `d`.
        """
        N, d = X.shape
        self.weights = np.ones(self.n_components) / self.n_components
        self.means = X[np.random.choice(N, self.n_components, replace=False)]
        self.covars = np.tile(np.eye(d), (self.n_components, 1, 1))

    def E_step(self, X):
        """
        Find the Expectation of the log-likelihood evaluated using the current estimate for the parameters.
        """
        N = X.shape[0]
        likelihoods = np.zeros((N, self.n_components))
        for i in range(self.n_components):
            likelihoods[:, i] = self.weights[i] * self._multivariate_normal_pdf(X, self.means[i], self.covars[i])
        responsibilities = likelihoods / likelihoods.sum(axis=1, keepdims=True)
        return responsibilities

    def M_step(self, X, responsibilities):
        """
        Updates parameters maximizing the expected log-likelihood found on the E step.
        """
        N, d = X.shape
        Nk = responsibilities.sum(axis=0)
        self.weights = Nk / N
        self.means = np.dot(responsibilities.T, X) / Nk[:, np.newaxis]
        for i in range(self.n_components):
            diff = X - self.means[i]
            self.covars[i] = np.dot(responsibilities[:, i] * diff.T, diff) / Nk[i]
            if np.linalg.det(self.covars[i]) == 0:  # If covariance matrix is singular
                self.covars[i] += self.reg_covar * np.eye(d)  # Regularize covariance matrix

    def fit(self, X, y=None):
        """
        Fit the parameters of the GMM on some training data.
        """
        self.initialize_params(X)
        prev_log_likelihood = None
        for _ in range(self.max_iter):
            responsibilities = self.E_step(X)
            self.M_step(X, responsibilities)
            log_likelihood = np.log(np.sum(responsibilities, axis=1)).sum()
            if prev_log_likelihood is not None and np.abs(log_likelihood - prev_log_likelihood) < self.tol:
                break
            prev_log_likelihood = log_likelihood

    def predict(self, X):
        """
        Predict the labels for the data samples in X using trained model.
        """
        print(type(X), len(X))
        responsibilities = self.E_step(X)
        return np.argmax(responsibilities, axis=1)

"""### Part 2: Background Subtraction

![traffic](./videos/traffic.gif)

In this question, you are required to extract the background image from a given set of training frames, and use the extracted background to display foreground objects in the test frames by subtracting that background image and then thresholding it accordingly.

In this question, we are going to try different baselines to extract background from low resolution camera footage:

1. Frame Averaging:
    - Just take the average of every training frame, which gives us an approximate background image.
    
2. GMM Per Pixel:
    - We will maintain per pixel GMMs of 2 components, and then fit these GMMs considering every training from for its corresponding pixel.
    - And then use these GMMs to predict the pixel labels for every subsequent frame.
    - Most of the time, the Gaussian with the higher weight corresponds to the background.
    - We can implement this in a simpler way but with worse prediction results, you can extract a mean background image similar to the first baseline above.
    - To extract the Mean background image, we can assign values of the Means corresponding to the highest weighted Gaussian for each pixel.
    - This method is much simpler to implement but, this could give worse results.

#### Extracting Frames from videos
"""

source_folder = 'videos'
video = 'traffic.gif'

source_path = f'./{video}'

data_folder = 'frames'

frames_path = f"./{data_folder}/{video.rsplit('.', 1)[0]}"
frames_path

# Commented out IPython magic to ensure Python compatibility.
# %%capture
# 
# !mkdir -p {frames_path} > /dev/null ;

# Commented out IPython magic to ensure Python compatibility.
# %%capture
# 
# !ffmpeg -i {source_path} {frames_path}/'frame_%04d.png' > /dev/null ;

"""#### Loading Frames"""

import glob

frames = []

for file_path in sorted(glob.glob(f'{frames_path}/*.png', recursive = False)):
    img = cv2.imread(file_path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    img = np.asarray(img, dtype=np.float64)
    img /= 255.0
    frames.append(img)

frames = np.asarray(frames, dtype=np.float64)
print(frames.shape)
frames

"""#### Splitting the data"""

from sklearn.model_selection import train_test_split

print(f'frame: {frames.shape}')

train_frames, test_frames = train_test_split(frames, train_size=0.6, shuffle=False)

print(f'train_frames: {train_frames.shape}')
print(f'test_frames: {test_frames.shape}')

"""Note: You may use helper libraries like `imageio` for working with GIFs.

```python
import imageio

def make_gif(img_list, gif_path, fps=10):
    imageio.mimsave(gif_path, img_list, fps=fps)
    return
```

#### Frame Averaging

Extract Background Image from the training data and display it.
"""

# your code here
background_image = np.mean(train_frames, axis=0)
print(background_image.shape)

plt.imshow(background_image)
plt.title('Background Image')
plt.axis('off')
plt.show()

"""#### GMMs per pixel

Create Set of GMMs for every pixel and fit them considering every training frame
"""

# your code here
def gmm_per_pixel(train_frames):
  n_frames, height, width, channels = train_frames.shape
  train_frames_2d = train_frames.reshape(n_frames, height * width, channels)
  pixel_gmms = []

  for pixel_index in range(height * width):
      pixel_values = train_frames_2d[:, pixel_index, :]

      gmm = GMM(n_components=10)
      gmm.fit(pixel_values)

      pixel_gmms.append(gmm)
  return pixel_gmms, height, width
pixel_gmms,height, width = gmm_per_pixel(train_frames)

# from sklearn.mixture import GaussianMixture

# # Reshape the training frames into a 2D array for easier iteration over pixels
# n_frames, height, width, channels = train_frames.shape
# train_frames_2d = train_frames.reshape(n_frames, height * width, channels)

# # Create an empty list to store GMMs for each pixel
# pixel_gmms = []

# # Iterate over each pixel
# for pixel_index in range(height * width):
#     # Extract pixel values from all frames for this pixel
#     pixel_values = train_frames_2d[:, pixel_index, :]

#     # Create and fit GMM for this pixel
#     gmm = GaussianMixture(n_components=2)  # You can adjust the number of components as needed
#     gmm.fit(pixel_values)

#     # Add trained GMM to the list
#     pixel_gmms.append(gmm)

"""#### Extract Background Image from the trained model"""

# your code here
n_frames, height, width, channels = train_frames.shape
def extract_background_image(pixel_gmms, height, width):
    background_means = np.zeros((height * width, 3))
    for i, gmm in enumerate(pixel_gmms):
        background_component_index = np.argmax(gmm.weights)
        background_means[i] = gmm.means[background_component_index]
    background_image = background_means.reshape(height, width, 3)
    return background_image

haha = extract_background_image(pixel_gmms, height, width)

plt.imshow(haha)
plt.title('Background Image')
plt.axis('off')
plt.show()

"""### Outputs

You can use the helper functions given below to display and save frames as videos, feel free to change them accordingly.
"""

from google.colab.patches import cv2_imshow

# helper functions

def display_frames(frames, fps=10.0):
    """
    Display the frames as a video.
    """
    eps = 0.0001

    wait_time = int(1000 // fps)

    for frame in frames:
        frame = frame.astype(np.float64)
        frame = (frame - frame.min()) * 255 / (frame.max() - frame.min() + eps)
        frame = frame.astype(np.uint8)

        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        cv2_imshow(frame)
        k = cv2.waitKey(wait_time)

        if k == ord('q'):
            print("Quitting...")
            break

    cv2.destroyAllWindows()


def save_frames(frames, fps=10.0, output_path='./results', file_name='output_video'):
    """
    Save the frames as a video.
    """
    os.makedirs(output_path, exist_ok=True)

    frame_rate = float(fps)
    frame_size = (frames[0].shape[1], frames[0].shape[0])

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    video_path = os.path.join(output_path, f"{file_name}.mp4")
    video_writer = cv2.VideoWriter(video_path, fourcc, frame_rate, frame_size)

    for frame in frames:
        frame = frame.astype(np.float64)
        frame = (frame - frame.min()) * 255 / (frame.max() - frame.min() + 1e-10)
        frame = frame.astype(np.uint8)

        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        video_writer.write(frame)

    video_writer.release()

    print(f"Video saved at: {video_path}")

"""#### Frame Averaging"""

processed_data = np.mean(train_frames, axis=0)
foreground_avg = np.abs(test_frames - processed_data)

# Display and save Frame Averaging results
display_frames([processed_data] + list(foreground_avg))
save_frames([processed_data] + list(foreground_avg), output_path='./results', file_name='frame_average_output')

"""#### GMMs per pixel"""

foreground_gmm = np.abs(test_frames - background_image)

# Check for NaN and infinite values, replace them with zeros to avoid dimension errors. (I encountered them earlier)
foreground_gmm[np.isnan(foreground_gmm)] = 0
foreground_gmm[np.isinf(foreground_gmm)] = 0

foreground_gmm_normalized = (foreground_gmm / np.max(foreground_gmm) * 255).astype(np.uint8)

# Threshold the resulting foreground images to seperate the value from the background, this is for my own reference
threshold = 25
foreground_thresholded = (foreground_gmm_normalized > threshold).astype(np.uint8) * 255

display_frames([background_image] + list(foreground_gmm))
save_frames([background_image] + list(foreground_gmm), output_path='./results', file_name='gmm_per_pixel_output')