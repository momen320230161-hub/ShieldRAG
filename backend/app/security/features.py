"""Fixed, versioned feature construction shared by training and inference."""
from sklearn.feature_extraction.text import TfidfVectorizer
import unicodedata

FEATURES = (('word',6000,(1,2)),('char_wb',8000,(3,5)))


def normalize(text):
    text=unicodedata.normalize('NFKC',text).casefold()
    return ' '.join(''.join(c for c in text if unicodedata.category(c) not in ('Cf','Mn') and c!='ـ').split())


def vectorizer(analyzer, vocabulary=None):
    _,limit,grams=next(f for f in FEATURES if f[0]==analyzer)
    return TfidfVectorizer(analyzer=analyzer,ngram_range=grams,preprocessor=normalize,lowercase=False,
                          sublinear_tf=True,max_features=limit,vocabulary=vocabulary)
