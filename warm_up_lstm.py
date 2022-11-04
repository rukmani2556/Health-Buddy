# -*- coding: utf-8 -*-
"""warm-up_LSTM.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1EOnkHEF012ZqKwgz8C7Rf1hQZvZYSXg6

retweet_file = open(path+'/temporal_retweet_count_t1m1.csv','r')
"""

# Basic packages
import pandas as pd 
import numpy as np
import re
import os
import collections
import matplotlib.pyplot as plt
from pathlib import Path
import sys
import regex
import math
import random

# Packages for data preparation
from sklearn.model_selection import train_test_split
from nltk.corpus import stopwords
from keras.preprocessing.text import Tokenizer
from keras.preprocessing.sequence import pad_sequences
from keras.utils.np_utils import to_categorical
from sklearn.preprocessing import LabelEncoder

# Packages for modeling
from keras import models
from keras import optimizers
from keras.models import Model
from keras import layers
from keras.layers import Dense, Embedding, LSTM, Input, SimpleRNN, TimeDistributed, Concatenate, BatchNormalization, LeakyReLU
from keras import regularizers
from keras import backend as K
from keras import initializers

import nltk
nltk.download('stopwords')

path = os.path.dirname(os.path.realpath(__file__))

"""Tweet text pre-processing"""

FLAGS = re.MULTILINE | re.DOTALL | regex.VERSION1

def hashtag(text):
    text = text.group()
    hashtag_body = text[1:]
    if hashtag_body.isupper():
        result = "<hashtag> {} <allcaps>".format(hashtag_body)
    else:
        result = " ".join(["<hashtag>"] + regex.split(r"(?=[A-Z])", hashtag_body, flags=FLAGS))
    return result

def allcaps(text):
    text = text.group()
    return text.lower() + " <allcaps>"


def tokenize(text):
    # Different regex parts for smiley faces
    eyes = r"[8:=;]"
    nose = r"['`\-]?"

    # function so code less repetitive
    def re_sub(pattern, repl):
        return re.sub(pattern, repl, text, flags=FLAGS)

    text = re_sub(r"https?:\/\/\S+\b|www\.(\w+\.)+\S*", "<url>")
    text = re_sub(r"/"," / ")
    text = re_sub(r"@\w+", "<user>")
    text = re_sub(r"{}{}[)dD]+|[)dD]+{}{}".format(eyes, nose, nose, eyes), "<smile>")
    text = re_sub(r"{}{}p+".format(eyes, nose), "<lolface>")
    text = re_sub(r"{}{}\(+|\)+{}{}".format(eyes, nose, nose, eyes), "<sadface>")
    text = re_sub(r"{}{}[\/|l*]".format(eyes, nose), "<neutralface>")
    text = re_sub(r"<3","<heart>")
    text = re_sub(r"[-+]?[.\d]*[\d]+[:,.\d]*", "<number>")
    text = re_sub(r"#\S+", hashtag)
    text = re_sub(r"([!?.]){2,}", r"\1 <repeat>")
    text = re_sub(r"\b(\S*?)(.)\2{2,}\b", r"\1\2 <elong>")

    ## -- I just don't understand why the Ruby script adds <allcaps> to everything so I limited the selection.
    # text = re_sub(r"([^a-z0-9()<>'`\-]){2,}", allcaps)
    text = re_sub(r"([A-Z]){2,}", allcaps)

    return text.lower()

NB_WORDS = 10000  # Parameter indicating the number of words we'll put in the dictionary
VAL_SIZE = 1000  # Size of the validation set
NB_START_EPOCHS = 2000  # Number of epochs we usually start to train with
BATCH_SIZE = 64  # Size of the batches used in the mini-batch gradient descent
MAX_LEN = 26  # Maximum number of words in a sequence
GLOVE_DIM = 100  # Number of dimensions of the GloVe word embeddings
LSTM_OUT = 512  # output dimension of language model lstm
NORMALIZE_TO = 100  # normalize the value of features between 0 to NORMALIZE_TO
RETWEETS_NORM_TO = 10
HOURS = 72  # number of hours the dataset was recorded for
RANDOM_NUM = random.randint(0,100)

def deep_model(model, X_train, u_train, y_train, X_valid, u_valid, y_valid):

    history = model.fit([X_train, u_train]
                       , y_train
                       , epochs=NB_START_EPOCHS
                       , batch_size=BATCH_SIZE
                       , validation_data=([X_valid, u_valid]
                                          , y_valid)
                       , verbose=1)

    return history

def remove_stopwords(input_text):
    '''
    Function to remove English stopwords from a Pandas Series.
    
    Parameters:
        input_text : text to clean
    Output:
        cleaned Pandas Series 
    '''
    stopwords_list = stopwords.words('english')
    # Some words which might indicate a certain sentiment are kept via a whitelist
    whitelist = ["n't", "not", "no"]
    words = input_text.split() 
    clean_words = [word for word in words if (word not in stopwords_list or word in whitelist) and len(word) > 1] 
    return " ".join(clean_words) 
    
def remove_mentions(input_text):
    '''
    Function to remove mentions, preceded by @, in a Pandas Series
    
    Parameters:
        input_text : text to clean
    Output:
        cleaned Pandas Series 
    '''
    return re.sub(r'@\w+', '', input_text)

def eval_metric(history, metric_name):
    '''
    Function to evaluate a trained model on a chosen metric. 
    Training and validation metric are plotted in a
    line chart for each epoch.
    
    Parameters:
        history : model training history
        metric_name : loss or accuracy
    Output:
        line chart with epochs of x-axis and metric on
        y-axis
    '''
    metric = history.history[metric_name]
    val_metric = history.history['val_' + metric_name]

    e = range(1, NB_START_EPOCHS + 1)

    plt.plot(e, metric, 'bo', label='Train ' + metric_name)
    plt.plot(e, val_metric, 'b', label='Validation ' + metric_name)
    plt.legend()
    plt.show()

def test_model(model, X_train, y_train, X_test, y_test, epoch_stop):
    '''
    Function to test the model on new data after training it
    on the full training data with the optimal number of epochs.
    
    Parameters:
        model : trained model
        X_train : training features
        y_train : training target
        X_test : test features
        y_test : test target
        epochs : optimal number of epochs
    Output:
        test accuracy and test loss
    '''
    model.fit(X_train
              , y_train
              , epochs=epoch_stop
              , batch_size=BATCH_SIZE
              , verbose=0)
    results = model.evaluate(X_test, y_test)
    
    return results

def poisson_loss(y_actual, y_predicted):
    loss = y_predicted - y_actual*K.log(y_predicted + 0.00001)
    return loss

def save_model(model):
    model.save(path+'/saved_models/encoder_model.h5')

def get_model():
    model = models.load_model(path+'/saved_models/encoder_model.h5', custom_objects={'poisson_loss': poisson_loss})
    return model

df = pd.read_csv(path+'/user_info_with_age.csv') 
df = df[['tweet_id', 'text', 'friends_count', 'followers_count', 'account_age', 'total_tweet_count', 'favourited_tweet_count']]      # X, y
df.text = df.text.apply(tokenize).apply(remove_stopwords).apply(remove_mentions)

dh = pd.read_csv(path+'/user_info_with_age.csv') 
user_featuers = ['friends_count', 'followers_count', 'account_age', 'total_tweet_count', 'favourited_tweet_count']

features = []
user_feature_count = len(user_featuers)
for i in range(user_feature_count-1):
    for j in range(i+1,user_feature_count):
        feature = dh[user_featuers[i]]*dh[user_featuers[j]]
        max_feature_value = feature.max()
        feature = (feature/max_feature_value)*NORMALIZE_TO
        features.append(feature)

features_count = len(features)
features = pd.concat(features, axis=1)

X_train, X_test, u_train, u_test = train_test_split(df.text, features, test_size=0.1, random_state=RANDOM_NUM)
print('# Train data samples:', X_train.shape[0])
print('# Test data samples:', X_test.shape[0])
assert X_train.shape[0] == u_train.shape[0]
assert X_test.shape[0] == u_test.shape[0]

seq_lengths = X_train.apply(lambda x: len(x.split(' ')))
tweet_stats = seq_lengths.describe()
MAX_LEN = int(tweet_stats['max'])
print('MAX_LEN: ',MAX_LEN)

dg = pd.read_csv(path+'/retweet_count_new_unnormalized.csv')
dg = dg[[str(HOURS)]]
max_retweet_count = dg.max()
dg = (dg/max_retweet_count)*RETWEETS_NORM_TO

X_train, X_test, y_train, y_test = train_test_split(df.text, dg, test_size=0.1, random_state=RANDOM_NUM)
assert X_train.shape[0] == y_train.shape[0]
assert X_test.shape[0] == y_test.shape[0]

tk = Tokenizer(num_words=NB_WORDS,
               filters='!"#$%&()*+,-./:;<=>?@[\\]^_`{|}~\t\n',
               lower=True,
               split=" ")
tk.fit_on_texts(X_train)      # creates a internal dictionary
X_train_seq = tk.texts_to_sequences(X_train)
X_test_seq = tk.texts_to_sequences(X_test)

X_train_seq_trunc = pad_sequences(X_train_seq, maxlen=MAX_LEN)
X_test_seq_trunc = pad_sequences(X_test_seq, maxlen=MAX_LEN)

X_train_emb, X_valid_emb, y_train_emb, y_valid_emb = train_test_split(X_train_seq_trunc, y_train, test_size=0.1, random_state=RANDOM_NUM)
X_train_emb, X_valid_emb, u_train_emb, u_valid_emb = train_test_split(X_train_seq_trunc, u_train, test_size=0.1, random_state=RANDOM_NUM)
assert X_valid_emb.shape[0] == y_valid_emb.shape[0]
assert X_train_emb.shape[0] == y_train_emb.shape[0]
print('Shape of training set:',X_train_emb.shape)
print('Shape of validation set:',X_valid_emb.shape)

"""Creating a Dictionary"""
print('creating Dictionary...')
glove_file = path+'/glove.twitter.27B.100d.txt'
# glove_file = 'customWE_100d.txt'
emb_dict = {}
glove = open(glove_file)
for line in glove:
    values = line.split()
    word = values[0]
    vector = np.asarray(values[1:], dtype='float32')
    emb_dict[word] = vector
glove.close()

print('Keywords...')
f = open(path+'/keywords.txt')
keywords = []
for line in f:
    word = line.split('  ')[0]
    word = tokenize(word)
    keywords.append(word)

print('words from custom Word Embedding...')
custom_glove_file = path+'/custom_WE.txt'
custom_glove = open(custom_glove_file)
for line in custom_glove:
    values = line.split()
    word = values[0]
    if word in keywords:
        print(word)
        vector = np.asarray(values[1:], dtype='float32')
        emb_dict[word] = vector
custom_glove.close()

emb_matrix = np.zeros((NB_WORDS, GLOVE_DIM))
for w, i in tk.word_index.items():
    # The word_index contains a token for all words of the training data so we need to limit that
    if i < NB_WORDS:
        vect = emb_dict.get(w)
        # Check if the word from the training data occurs in the GloVe word embeddings
        # Otherwise the vector is kept with only zeros
        if vect is not None:
            emb_matrix[i] = vect
    else:
        break

"""Building Model"""

# This is for training
encoder_inputs = Input(shape=(MAX_LEN, ), name='input_1')
embedding = Embedding(NB_WORDS, GLOVE_DIM, name='embedding_1')
embedding_inputs = embedding(encoder_inputs)
encoder = LSTM(LSTM_OUT, dropout_U = 0.3, dropout_W = 0.3, name='lstm_1')
lstm_output = encoder(embedding_inputs)
user_info_inputs = Input(shape=(features_count,), name='input_2')
dense1 = Dense(units=128, name='dense_1')     # Whc
full_info = Concatenate(name='concatenate_1')([lstm_output, user_info_inputs])
encoder_output_dense1 = dense1(full_info)

# this is to calculate number of retweets at last hour, we dont need this during end-to-end.
leaky_relu = LeakyReLU()
dense2 = Dense(units=1, activation='relu', name='dense_2')
encoder_output_lrelu = leaky_relu(encoder_output_dense1)
encoder_output = dense2(encoder_output_lrelu)

# initializing model
encoder_model = Model([encoder_inputs, user_info_inputs], encoder_output)
encoder_model.compile(optimizer='Adam', loss=poisson_loss)
encoder_model.summary()

# This is what makes model use pre-trained weights
encoder_model.layers[1].set_weights([emb_matrix])
encoder_model.layers[1].trainable = False

glove_history = deep_model(encoder_model, X_train_emb, u_train_emb, y_train_emb, X_valid_emb, u_valid_emb, y_valid_emb)

save_model(encoder_model)

with open(path+'/loss_log_mse.txt', 'w') as f:
    for key, value in glove_history.history.items():
        f.write('%s:%s\n' % (key, value))