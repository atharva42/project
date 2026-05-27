# POS Tagging with LSTM

This README is forcode for Part-of-Speech (POS) tagging using a Long Short-Term Memory (LSTM) neural network and FeedForward Neural Network(FFNN) implemented in PyTorch. 

## Instructions

### Execution
To execute the code, follow these steps:

1. Make sure you have Python installed on your system.
2. Clone this repository.
3. Ensure you have all required libraries installed. You can install them via pip:
    ```
    pip install torch numpy conllu scikit-learn matplotlib
    ```
4. Download the datasets:
   - en_atis-ud-train.conllu
   - en_atis-ud-dev.conllu
   - en_atis-ud-test.conllu
5. Place the datasets in the same directory as the code.
6. Run the `pos_tagging_lstm.py` script:
    ```
    python pos_tagging_lstm.py
    ```

### Pretrained Model
A pretrained model is provided in the script. You can directly use it for POS tagging without training.

### Implementation Assumptions
- The code assumes that the datasets are in the CoNLL-U format.
- It assumes that the datasets are tokenized and annotated with POS tags.
- Punctuation tokens are excluded during data loading.
- The LSTM model architecture consists of word embeddings, LSTM layers, and linear layers.
- Cross-entropy loss and SGD optimizer are used for training.
- The code assumes that the best configuration is chosen based on development set accuracy.

# FeedForward Neural Network(FFNN)
## Analysis
### Code Overview
- **Data Preparation**: The code reads data from CoNLL-U files, preprocesses tokens and POS tags, and generates features and labels.
- **Model Definition**: A FFNN model is defined using PyTorch, with configurable embedding dimension, hidden layer dimensions, and output dimension.
- **Training**: The model is trained using Adam optimization and cross-entropy loss.
- **Evaluation**: Evaluation is performed on development and test sets using classification metrics like accuracy, classification report, and confusion matrix.
- **Hyperparameter Tuning**: The script allows experimenting with different hyperparameters and comparing their effects on model performance.
- **Visualization**: Matplotlib and Seaborn are used for visualizing accuracy and confusion matrices.

### Performance
- **Training Loss**: The training loss decreases over epochs, indicating successful training.
- **Development Set Accuracy**: Accuracy on the development set is monitored during training for early stopping and hyperparameter tuning.
- **Test Set Accuracy**: Final accuracy on the test set is reported after training and evaluation.
- **Confusion Matrices**: Confusion matrices provide insights into the model's performance across different POS tags.

### Hyperparameter Tuning
- The script allows experimenting with various hyperparameters such as context window size, embedding dimension, hidden layer dimensions, and learning rate.
- Different configurations are evaluated on the development set, and the best configuration is selected based on performance metrics.

### Visualization
- Matplotlib and Seaborn are used to plot accuracy trends over epochs and visualize confusion matrices.



# Long Short-Term Memory (LSTM)
## Analysis

### Code Overview
- **Data Loading**: The code loads training, development, and test datasets from files in CoNLL-U format.
- **Model Definition**: An LSTM model is defined using PyTorch, with configurable embedding dimension, hidden dimension, activation function, number of layers, and bidirectionality.
- **Training**: The model is trained using SGD optimization on the training set.
- **Evaluation**: Evaluation is performed on the development set to monitor model performance during training. Final evaluation is done on the test set.
- **Hyperparameter Tuning**: Experiments are conducted with different hyperparameter configurations, and the best configuration is selected based on development set accuracy.

### Performance
- **Training Loss**: The training loss decreases over epochs, indicating that the model is learning.
- **Development Set Accuracy**: The accuracy on the development set is monitored during training. It helps in early stopping and hyperparameter tuning.
- **Test Accuracy**: The final accuracy on the test set is reported after training and evaluation.

### Hyperparameter Tuning
- The script conducts experiments with different configurations (varying embedding dimension, hidden dimension, activation function, etc.).
- It selects the configuration with the highest accuracy on the development set as the best configuration.
- The best model is then trained using this configuration and evaluated on the test set.

### Visualization
- The script provides visualization of epoch vs. development set accuracy for different configurations using Matplotlib.
