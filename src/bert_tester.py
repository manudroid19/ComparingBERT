import warnings
import torch
from sklearn.metrics.pairwise import cosine_similarity
from transformers import BertTokenizer, BertModel, RobertaModel, RobertaTokenizer, DistilBertTokenizer, DistilBertModel
from model_tester import ModelTester

warnings.filterwarnings("ignore", category=UserWarning)


class BertTester(ModelTester):
    def __init__(self, pairs, similarity_type, version, combine_method):
        super().__init__(pairs)
        self.combine_method = combine_method
        self.similarity_type = similarity_type
        tokenizers = {
            'roberta-base': RobertaTokenizer,
            'distilbert-base-uncased': DistilBertTokenizer
        }
        models = {
            'roberta-base': RobertaModel,
            'distilbert-base-uncased': DistilBertModel
        }
        POSs = {
            'head': 2,
            'dep-subj': 1,
            'dep-obj': 3,
            'dep': 1
        }

        # Load pre-trained model tokenizer (vocabulary)
        self.tokenizer = tokenizers.get(version, BertTokenizer).from_pretrained(version)
        # Load pre-trained model (weights)
        self.model = models.get(version, BertModel).from_pretrained(version, output_hidden_states=True)
        # Position of the contextualized word in the sentence.
        self.POS = POSs.get(self.similarity_type)
        self.name = version

    def process_pairs(self):
        model_similarities = []
        i = 0
        for tupla in self.pairs:
            model_similarities.append(self.procesar_tupla(tupla, self.POS))
            i += 1
            print("\r\tProgress {:2.1%}".format(i / len(self.pairs)), end='')
        return model_similarities

    def __str__(self):
        return self.name + "-" + self.similarity_type + "-" + self.combine_method

    def procesar_tupla(self, tupla, POS):
        sent1 = tupla[0].replace("@", " ")
        sent2 = tupla[1].replace("@", " ")
        POS = int(POS)

        marked_text = "[CLS] " + sent1 + " [SEP]"
        tokenized_text = self.tokenizer.tokenize(marked_text)
        indexed_tokens = self.tokenizer.convert_tokens_to_ids(tokenized_text)

        segments_ids = [1] * len(tokenized_text)
        tokens_tensor = torch.tensor([indexed_tokens])
        segments_tensors = torch.tensor([segments_ids])

        # Predict hidden states features for each layer
        with torch.no_grad():
            encoded_layers = self.model(tokens_tensor, segments_tensors)

        batch_i = 0
        pos = 0
        token_embeddings = []
        pos1 = 0
        # For each token in the sentence...
        for token_i in range(len(tokenized_text)):
            # for token_i,tok in enumerate(tokenized_text):
            # Holds 12 layers of hidden states for each token
            tok = tokenized_text[token_i]
            # print(tok,pos,token_i)
            if tok.startswith("##"):
                continue
            # print(tok,POS,pos,token_i)
            hidden_layers = []
            # For each of the 12 layers...
            if (len(encoded_layers) > 2):
                layer = 2
            else:
                layer = 1
            for layer_i in range(len(encoded_layers[layer])):
                # Lookup the vector for `token_i` in `layer_i`
                vec = encoded_layers[layer][layer_i][batch_i][token_i]
                # vec = encoded_layers[layer_i][batch_i][token_i]
                hidden_layers.append(vec)
            token_embeddings.append(hidden_layers)
            if pos == POS:
                pos1 = pos
                # print(tok,pos,token_i)
            pos += 1

        if self.combine_method == "sum":
            combined_last_4_layers = [torch.sum(torch.stack(layer)[-4:], 0) for layer in token_embeddings]
        elif self.combine_method == "concat":
            combined_last_4_layers = [torch.cat((layer[-1], layer[-2], layer[-3], layer[-4]), 0) for layer in
                                      token_embeddings]
        sentence1_vector = combined_last_4_layers[pos1].reshape(1, -1)

        ###SENTENCE 2
        marked_text = "[CLS] " + sent2 + " [SEP]"
        tokenized_text = self.tokenizer.tokenize(marked_text)
        indexed_tokens = self.tokenizer.convert_tokens_to_ids(tokenized_text)

        segments_ids = [1] * len(tokenized_text)
        tokens_tensor = torch.tensor([indexed_tokens])
        segments_tensors = torch.tensor([segments_ids])

        # Predict hidden states features for each layer
        with torch.no_grad():
            encoded_layers = self.model(tokens_tensor, segments_tensors)

        layer_i = 0
        batch_i = 0
        token_i = 0
        pos = 0
        token_embeddings = []

        # For each token in the sentence...
        for token_i in range(len(tokenized_text)):
            # Holds 12 layers of hidden states for each token
            tok = tokenized_text[token_i]
            if tok.startswith("##"):
                continue
            hidden_layers = []
            if (len(encoded_layers) > 2):
                layer = 2
            else:
                layer = 1
            # For each of the 12 layers...
            for layer_i in range(len(encoded_layers[layer])):
                # Lookup the vector for `token_i` in `layer_i`
                vec = encoded_layers[layer][layer_i][batch_i][token_i]
                # vec = encoded_layers[layer_i][batch_i][token_i]
                hidden_layers.append(vec)
            token_embeddings.append(hidden_layers)
            if pos == POS:
                pos1 = pos
                # print(tok,pos,token_i)
                # print (tokenized_text[token_i],token_i,pos)
            pos += 1

        if self.combine_method == "sum":
            combined_last_4_layers = [torch.sum(torch.stack(layer)[-4:], 0) for layer in token_embeddings]
        elif self.combine_method == "concat":
            combined_last_4_layers = [torch.cat((layer[-1], layer[-2], layer[-3], layer[-4]), 0) for layer in
                                      token_embeddings]

        # concatenated_last_4_layers = [torch.cat((layer[-1], layer[-2], layer[-3], layer[-4], layer[-5], layer[-6]), 0) for layer in token_embeddings]
        # summed_last_4_layers = [torch.stack(layer)[-2:]  for layer in token_embeddings]
        # summed_last_4_layers = [torch.stack(layer)[-2:]  for layer in token_embeddings]
        # simil1 = cosine_similarity(summed_last_4_layers[pos1].reshape(1,-1), summed_last_4_layers[pos2].reshape(1,-1))[0][0]
        sentence2_vector = combined_last_4_layers[pos1].reshape(1, -1)
        return cosine_similarity(sentence1_vector.reshape(1, -1), sentence2_vector.reshape(1, -1))[0][0]
