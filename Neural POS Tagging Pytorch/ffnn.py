import numpy as np
import conllu
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.metrics import classification_report


def data_preprocess(data, p, s):
    X = []
    y = []
    for tokens, tags in data:
        formatted_tokens = ["<s>"] * p + tokens + ["</e>"] * s
        padded_pos_tags = ["<s>"] * p + tags + ["</e>"] * s
        for i in range(p, len(tokens) + p): 
            prev_context = formatted_tokens[i-p:i]
            next_context = formatted_tokens[i+1:i+s+1]
            current_token = formatted_tokens[i]
            context_data = []
            for token in prev_context + [current_token] + next_context:
                if token in word2idx:
                    context_data.append(word2idx[token])
                else:
                    context_data.append(word2idx["<UNK>"])
            X.append(context_data)
            y.append(padded_pos_tags[i])
    return X, y
# Function to read CoNLL-U file and extract relevant columns
def parse_file(file_path):
    data = []
    with open(file_path, "r", encoding="utf-8") as f:
        sentences = conllu.parse(f.read())
        for sentence in sentences:
            tokens = [token["lemma"].lower() for token in sentence]
            pos_tags = [token["upos"] for token in sentence]
            data.append((tokens, pos_tags))
    return data

# Set context window size
p = 2
s = 3

# Read data from CoNLL-U files
training_data = parse_file("en_atis-ud-train.conllu")
dev_data = parse_file("en_atis-ud-dev.conllu")
testing_data = parse_file("en_atis-ud-test.conllu")

vocab = set(token for stuff in training_data + dev_data + testing_data for token in stuff[0])
vocab_size = len(vocab)
word2idx = {token: index for index, token in enumerate(vocab)}
word2idx["<UNK>"] = len(word2idx) 

X_train, y_train = data_preprocess(training_data, p, s)
X_dev, y_dev = data_preprocess(dev_data, p, s)
X_test, y_test = data_preprocess(testing_data, p, s)

set_label = set(y_train)
for label in y_dev + y_test:
    if label not in set_label:
        set_label.add(label)

label2idx = {label: index for index, label in enumerate(set_label)}
y_train = [label2idx[label] for label in y_train]
y_dev = [label2idx.get(label, -1) for label in y_dev]
y_test = [label2idx.get(label, -1) for label in y_test]

vocab = set([token for data in X_train + X_dev + X_test for token in data])
vocab_size = len(vocab)

word2idx = {word: index for index, word in enumerate(vocab)}
word2idx["<UNK>"] = len(word2idx)
max_seq_length = p + s + 1
X_train = [[word2idx[token] if token in word2idx else word2idx["<UNK>"] for token in context] for context in X_train]
X_dev = [[word2idx[token] if token in word2idx else word2idx["<UNK>"] for token in context] for context in X_dev]
X_test = [[word2idx[token] if token in word2idx else word2idx["<UNK>"] for token in context] for context in X_test]

X_train_padded = [sequence[:max_seq_length] + [0] * (max_seq_length - len(sequence)) for sequence in X_train]
X_dev_padded = [sequence[:max_seq_length] + [0] * (max_seq_length - len(sequence)) for sequence in X_dev]
X_test_padded = [sequence[:max_seq_length] + [0] * (max_seq_length - len(sequence)) for sequence in X_test]

X_train_tensor = torch.LongTensor(X_train_padded)
y_train_tensor = torch.LongTensor(y_train)
X_dev_tensor = torch.LongTensor(X_dev_padded)
y_dev_tensor = torch.LongTensor(y_dev)
X_test_tensor = torch.LongTensor(X_test_padded)
y_test_tensor = torch.LongTensor(y_test)

# Define FFNN model
class FFNN(nn.Module):
    def __init__(self, vocab_size, embedding_dim, hidden_dim, output_dim):
        super(FFNN, self).__init__()
        self.embedding = nn.Embedding(vocab_size, embedding_dim)
        self.fc1 = nn.Linear((p+s+1) * embedding_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, output_dim)

    def forward(self, x):
        embedded = self.embedding(x).view(-1, (p+s+1) * embedding_dim)
        out = torch.relu(self.fc1(embedded))
        out = self.fc2(out)
        return out

embedding_dim = 100
hidden_dims = 128
output_dim = len(label2idx)
learning_rate = 0.01
num_epochs = 100

model = FFNN(vocab_size, embedding_dim, hidden_dims, output_dim)
criterion = nn.CrossEntropyLoss()
optimizer = optim.Adam(model.parameters(), lr=learning_rate)

# Training loop
for epoch in range(num_epochs):
    model.train()
    optimizer.zero_grad()
    outputs = model(X_train_tensor)
    loss = criterion(outputs, y_train_tensor)
    loss.backward()
    optimizer.step()

model.eval()
with torch.no_grad():
    outputs_dev = model(X_dev_tensor)
    _, predicted_dev = torch.max(outputs_dev, 1)
    print("Development Set:")
    print(classification_report(y_dev, predicted_dev.numpy()))

    outputs_test = model(X_test_tensor)
    _, predicted_test = torch.max(outputs_test, 1)
    print("Test Set:")
    print(classification_report(y_test, predicted_test.numpy()))

model_path = "/content/drive/MyDrive/Data/ffnn_model.pt"
torch.save(model.state_dict(), model_path)
print(f"Model is stored at : {model_path}")

from sklearn.metrics import classification_report
import matplotlib.pyplot as plt

# Define FFNN model
class FFNN(nn.Module):
    def __init__(self, vocab_size, embedding_dim, hidden_dim, output_dim):
        super(FFNN, self).__init__()
        self.embedding = nn.Embedding(vocab_size, embedding_dim)
        self.fc1 = nn.Linear((p+s+1) * embedding_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, output_dim)

    def forward(self, x):
        embedded = self.embedding(x).view(-1, (p+s+1) * embedding_dim)
        out = torch.relu(self.fc1(embedded))
        out = self.fc2(out)
        return out

def train_and_evaluate_model(context_window):
    p = s = context_window

    model = FFNN(vocab_size, embedding_dim, hidden_dims, output_dim)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=learning_rate)

    for epoch in range(num_epochs):
        model.train()
        optimizer.zero_grad()
        outputs = model(X_train_tensor)
        loss = criterion(outputs, y_train_tensor)
        loss.backward()
        optimizer.step()

    model.eval()
    with torch.no_grad():
        outputs_dev = model(X_dev_tensor)
        _, predicted_dev = torch.max(outputs_dev, 1)
        accuracy_dev = np.mean(np.array(predicted_dev.numpy()) == np.array(y_dev))

        outputs_test = model(X_test_tensor)
        _, predicted_test = torch.max(outputs_test, 1)
        accuracy_test = np.mean(np.array(predicted_test.numpy()) == np.array(y_test))

    return accuracy_dev, accuracy_test

context_window_sizes = range(5)
dev_accuracies = []
test_accuracies = []

for window in context_window_sizes:
    acc_dev, acc_test = train_and_evaluate_model(window)
    dev_accuracies.append(acc_dev)
    test_accuracies.append(acc_test)

# Plot the results
plt.plot(context_window_sizes, dev_accuracies, label='Dev Set Accuracy')
plt.plot(context_window_sizes, test_accuracies, label='Test Set Accuracy')
plt.xlabel('Context Window Size')
plt.ylabel('Accuracy')
plt.legend()
plt.show()

from sklearn.metrics import classification_report, confusion_matrix
import seaborn as sns
def train_model(context_window_size):
    p = s = context_window_size

    model = FFNN(vocab_size, embedding_dim, hidden_dims, output_dim)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=learning_rate)

    for epoch in range(num_epochs):
        model.train()
        optimizer.zero_grad()
        outputs = model(X_train_tensor)
        loss = criterion(outputs, y_train_tensor)
        loss.backward()
        optimizer.step()

    model.eval()
    with torch.no_grad():
        outputs_dev = model(X_dev_tensor)
        _, predicted_dev = torch.max(outputs_dev, 1)

        outputs_test = model(X_test_tensor)
        _, predicted_test = torch.max(outputs_test, 1)

    accuracy_dev = np.mean(np.array(predicted_dev.numpy()) == np.array(y_dev))
    accuracy_test = np.mean(np.array(predicted_test.numpy()) == np.array(y_test))

    conf_matrix_dev = confusion_matrix(y_dev, predicted_dev.numpy())
    conf_matrix_test = confusion_matrix(y_test, predicted_test.numpy())

    return accuracy_dev, accuracy_test, conf_matrix_dev, conf_matrix_test

context_window_sizes = range(5)
dev_accuracies = []
test_accuracies = []
conf_matrices_dev = []
conf_matrices_test = []

for window_size in context_window_sizes:
    acc_dev, acc_test, conf_matrix_dev, conf_matrix_test = train_and_evaluate_model(window_size)
    dev_accuracies.append(acc_dev)
    test_accuracies.append(acc_test)
    conf_matrices_dev.append(conf_matrix_dev)
    conf_matrices_test.append(conf_matrix_test)

# Plot the results
plt.plot(context_window_sizes, dev_accuracies, label='Dev Set Accuracy')
plt.plot(context_window_sizes, test_accuracies, label='Test Set Accuracy')
plt.xlabel('Context Window Size')
plt.ylabel('Accuracy')
plt.legend()
plt.show()

# Display confusion matrices
for i, window in enumerate(context_window_sizes):
    print(f"Confusion Matrix for Dev Set (Context Window Size = {window}):")
    print(conf_matrices_dev[i])
    print("\n")
    print(f"Confusion Matrix for Test Set (Context Window Size = {window}):")
    print(conf_matrices_test[i])
    print("\n")

# Load the model
loaded_model = FFNN(vocab_size, embedding_dim, hidden_dims, output_dim)
loaded_model.load_state_dict(torch.load(model_path))
loaded_model.eval()  # Set the model to evaluation mode
model.load_state_dict(torch.load(model_path, map_location=torch.device('cpu')))
model.eval()
print("Model loaded successfully.")

import matplotlib.pyplot as plt

# Experiment 1
embedding_dim_exp1 = 100
hidden_dim_exp1 = 128
output_dim_exp1 = len(label2idx)
learning_rate_exp1 = 0.01
num_epochs_exp1 = 50

model_exp1 = FFNN(vocab_size, embedding_dim_exp1, hidden_dim_exp1, output_dim_exp1)
train_losses_exp1, dev_accuracies_exp1 = train_model(model_exp1, X_train_tensor, y_train_tensor, X_dev_tensor, y_dev_tensor, num_epochs_exp1, learning_rate_exp1)

# Experiment 2 (Modify hyperparameters as needed)
embedding_dim_exp2 = 100
hidden_dim_exp2 = 256
output_dim_exp2 = len(label2idx)
learning_rate_exp2 = 0.005
num_epochs_exp2 = 50

model_exp2 = FFNN(vocab_size, embedding_dim_exp2, hidden_dim_exp2, output_dim_exp2)
train_losses_exp2, dev_accuracies_exp2 = train_model(model_exp2, X_train_tensor, y_train_tensor, X_dev_tensor, y_dev_tensor, num_epochs_exp2, learning_rate_exp2)

embedding_dim_exp3 = 100
hidden_dim_exp3 = 512
output_dim_exp3 = len(label2idx)
learning_rate_exp3 = 0.001
num_epochs_exp3 = 50

model_exp3 = FFNN(vocab_size, embedding_dim_exp3, hidden_dim_exp3, output_dim_exp3)
train_losses_exp3, dev_accuracies_exp3 = train_model(model_exp3, X_train_tensor, y_train_tensor, X_dev_tensor, y_dev_tensor, num_epochs_exp3, learning_rate_exp3)

plt.figure(figsize=(12, 6))
plt.plot(range(1, num_epochs_exp1 + 1), train_losses_exp1, label='Experiment 1')
plt.plot(range(1, num_epochs_exp2 + 1), train_losses_exp2, label='Experiment 2')
plt.plot(range(1, num_epochs_exp3 + 1), train_losses_exp3, label='Experiment 3')
plt.xlabel('Epochs')
plt.ylabel('Training Loss')
plt.legend()
plt.show()

plt.figure(figsize=(12, 6))
plt.plot(range(1, num_epochs_exp1 + 1), dev_accuracies_exp1, label='Experiment 1')
plt.plot(range(1, num_epochs_exp2 + 1), dev_accuracies_exp2, label='Experiment 2')
plt.plot(range(1, num_epochs_exp3 + 1), dev_accuracies_exp3, label='Experiment 3')
plt.xlabel('Epochs')
plt.ylabel('Dev Set Accuracy')
plt.legend()
plt.show()

model_exp1.eval()
with torch.no_grad():
    outputs_test_exp1 = model_exp1(X_test_tensor)
    _, predicted_test_exp1 = torch.max(outputs_test_exp1, 1)
    print("Test Set - Experiment 2:")
    print(classification_report(y_test, predicted_test_exp1.numpy()))

def pos_tag(sentence, model, word2idx, max_seq_length):
    tokens = sentence.lower().split()
    index = [word2idx.get(token,778) for token in tokens]
    padded_sequence = index[:max_seq_length] + [0] * (max_seq_length - len(ind))

    input_tensor = torch.LongTensor([padded_sequence])

    with torch.no_grad():
        output = model(input_tensor)
        _, predicted_label = torch.max(output, 1)
        predicted_label = predicted_label.item()

    idx2label = {idx: label for label, idx in label2idx.items()}
    predicted_label = idx2label[predicted_label]

    return list(zip(tokens, [predicted_label] * len(tokens)))

input_sentence = input()
pos_tags = pos_tag(input_sentence, loaded_model, global_word2idx, max_seq_length)
for content in pos_tags:
  print(content[0],content[1])

