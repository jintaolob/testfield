from nltk.classify.scikitlearn import SklearnClassifier
from sklearn.naive_bayes import MultinomialNB
from contrai_cradle.abstracts.MLAbstract import MLAbstract

class MultinomialNBClassifying(MLAbstract):
    """
    Naive Bayes with multinomial estimator
    """
    _model_type = "Multinomial NB"
    _parameters = ""
    _parametric = False

    def _train(self, train_data):
        self._model  = SklearnClassifier(MultinomialNB())
        self._model.train(train_data)
        return self._model