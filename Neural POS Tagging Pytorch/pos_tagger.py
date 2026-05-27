import torch
import torch.nn as nn
import argparse
import ffnn_model.pt
import lstm_model.pt

def read_conllu(file_path):
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

train_data = read_conllu("en_atis-ud-train.conllu")
test_data = read_conllu("en_atis-ud-test.conllu")
dev_data = read_conllu("en_atis-ud-dev.conllu")

vocab = set(token for sublist in train_data + dev_data + test_data for token in sublist[0])
vocab_size = len(vocab)
word2idx = {word: idx for idx, word in enumerate(vocab)}
word2idx["<UNK>"] = len(word2idx)  

class FFNN(nn.Module):
    def _init_(self, vocab_size, embedding_dim, hidden_dim, output_dim):
        super(FFNN, self)._init_()
        self.embedding = nn.Embedding(vocab_size, embedding_dim)
        self.fc1 = nn.Linear((p+s+1) * embedding_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, output_dim)

    def forward(self, x):
        embedded = self.embedding(x).view(-1, (p+s+1) * embedding_dim)
        out = torch.relu(self.fc1(embedded))
        out = self.fc2(out)
        return out

class LSTMTagger(nn.Module):
    def _init_(self, embedding_dim, hidden_dim, vocab_size, tagset_size, activation='tanh', num_layers=1, bidirectional=False):
        super(LSTMTagger, self)._init_()
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.bidirectional = bidirectional

        self.word_embeddings = nn.Embedding(vocab_size, embedding_dim)

        self.lstm = nn.LSTM(embedding_dim, hidden_dim, num_layers=num_layers, bidirectional=bidirectional)

        if bidirectional:
            self.hidden2tag = nn.Linear(hidden_dim * 2, tagset_size)
        else:
            self.hidden2tag = nn.Linear(hidden_dim, tagset_size)

        self.activation = getattr(F, activation, None)

    def forward(self, sentence):
        embeds = self.word_embeddings(sentence)
        lstm_out, _ = self.lstm(embeds.view(len(sentence), 1, -1))
        tag_space = self.hidden2tag(lstm_out.view(len(sentence), -1))
        tag_scores = nn.functional.log_softmax(tag_space, dim=1)
        return tag_scores


def evaluate(model, sentences, tags, word_to_idx, tag_to_idx):
    y_true = []
    y_pred = []

    for sent, true_tags in zip(sentences, tags):
        predicted_tags = predict(model, sent, word_to_idx, tag_to_idx)
        y_true.extend(true_tags)
        y_pred.extend(predicted_tags)

    accuracy = accuracy_score(y_true, y_pred)
    recall_micro = recall_score(y_true, y_pred, average='micro')
    recall_macro = recall_score(y_true, y_pred, average='macro')
    f1_micro = f1_score(y_true, y_pred, average='micro')
    f1_macro = f1_score(y_true, y_pred, average='macro')

    confusion_mat = confusion_matrix(y_true, y_pred)

    return accuracy, recall_micro, recall_macro, f1_micro, f1_macro, confusion_mat


def evaluate_model(model, sentences, tags, word_to_idx, tag_to_idx):
    y_true = []
    y_pred = []

    for sent, true_tags in zip(sentences, tags):
        predicted_tags = predict(model, sent, word_to_idx, tag_to_idx)
        y_true.extend(true_tags)
        y_pred.extend(predicted_tags)

    report = classification_report(y_true, y_pred, labels=list(tag_to_idx.keys()), target_names=list(tag_to_idx.keys()), output_dict=True)
    return report

def extract_sentences_and_tags(data):
    sentences = []
    tags = []
    for sentence in data:
        sent = []
        tag = []
        for token in sentence:
            if token['upostag'] != 'PUNCT':
                sent.append(token['form'].lower())
                tag.append(token['upostag'])
        sentences.append(sent)
        tags.append(tag)
    return sentences, tags

train_sentences, train_tags = extract_sentences_and_tags(train_data)
dev_sentences, dev_tags = extract_sentences_and_tags(dev_data)
test_sentences, test_tags = extract_sentences_and_tags(test_data)

def create_vocab_tagset(sentences, tags):
    word_to_idx = {}
    tag_to_idx = {}
    for sentence, tag_seq in zip(sentences, tags):
        for word in sentence:
            if word not in word_to_idx:
                word_to_idx[word] = len(word_to_idx)
        for tag in tag_seq:
            if tag not in tag_to_idx:
                tag_to_idx[tag] = len(tag_to_idx)
    return word_to_idx, tag_to_idx

word_to_idx, tag_to_idx = create_vocab_tagset(train_sentences, train_tags)

embedding_dim = 100
hidden_dim = 128
vocab_size = len(word_to_idx)
tagset_size = len(tag_to_idx)
num_epochs = 30
learning_rate = 0.01

def calculate_accuracy(model, sentences, tags, word_to_idx, tag_to_idx):
    correct = 0
    total = 0
    for sent, true_tags in zip(sentences, tags):
        predicted_tags = predict(model, sent, word_to_idx, tag_to_idx)
        correct += sum(p == t for p, t in zip(predicted_tags, true_tags))
        total += len(true_tags)
    accuracy = correct / total
    return accuracy

def create_vocab_tagset(sentences, tags):
    word_to_idx = {'<unk>': 0}
    tag_to_idx = {}
    for sentence, tag_seq in zip(sentences, tags):
        for word in sentence:
            if word not in word_to_idx:
                word_to_idx[word] = len(word_to_idx)
        for tag in tag_seq:
            if tag not in tag_to_idx:
                tag_to_idx[tag] = len(tag_to_idx)
    return word_to_idx, tag_to_idx
def prepare_sequence(seq, to_idx):
    return torch.tensor([to_idx.get(w, 0) for w in seq], dtype=torch.long)

def preprocess_input_text(input_sentence, word2idx, max_seq_length):
    tokens = input_sentence.split()
    indices = [word2idx.get(token, word2idx["<UNK>"]) for token in tokens]
    padded_sequence = indices[:max_seq_length] + [0] * (max_seq_length - len(indices))
    return padded_sequence

def pos_tag_sentence(sentence, model, word2idx, max_seq_length):
    input_indices = preprocess_input_text(sentence, word2idx, max_seq_length)
    input_tensor = torch.LongTensor([input_indices])

    with torch.no_grad():
        output = model(input_tensor)
        _, predicted_label = torch.max(output, 1)
        predicted_label = predicted_label.item()

    idx2label = {idx: label for label, idx in label2idx.items()}
    predicted_label = idx2label[predicted_label]

    return list(zip(sentence.split(), [predicted_label] * len(sentence.split())))

if _name_ == "_main_":
    parser = argparse.ArgumentParser(description="POS Tagger")
    parser.add_argument("-f", action="store_true", help="Use FFNN model")
    parser.add_argument("-r", action="store_true", help="Use RNN model")
    args = parser.parse_args()

    if args.f:
        # Load your trained model
        model_path="ffnn_model.pt"
        loaded_model = FFNN(vocab_size, embedding_dim, hidden_dims, output_dim)
        loaded_model.load_state_dict(torch.load(model_path))
        loaded_model.eval()
    elif args.r:
        # Load your trained model
        model_path="lstm_model.pt"
        loaded_model = LSTMTagger(embedding_dim, hidden_dims, vocab_size, tagset_size, activation='relu', num_layers=2, bidirectional=True)
        loaded_model.load_state_dict(torch.load(model_path))
        loaded_model.eval()
    else:
        print("Please specify either -f for FFNN or -r for RNN")
        exit()

    while True:
        input_sentence = input("Enter a sentence (or 'exit' to quit): ")
        if input_sentence.lower() == "exit":
            break

        pos_tags = pos_tag_sentence(input_sentence, loaded_model, word2idx, max_seq_length)
        for token, pos_tag in pos_tags:
            print(f"{token}\t{pos_tag}")
