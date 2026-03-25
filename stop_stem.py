import nltk
from nltk.stem import PorterStemmer
import os

class StopStem:
    def __init__(self, stopwords_file):
        self.stopwords = set()
        if os.path.exists(stopwords_file):
            with open(stopwords_file, 'r', encoding='utf-8') as f:
                for line in f:
                    w = line.strip()
                    if w:
                        self.stopwords.add(w)
        
        self.stemmer = PorterStemmer()

    def is_stop_word(self, word):
        return word in self.stopwords

    def stem(self, word):
        return self.stemmer.stem(word)