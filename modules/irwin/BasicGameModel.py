import numpy as np
import logging
import os

from random import shuffle

from collections import namedtuple

from keras.models import load_model, Model
from keras.layers import Dropout, Flatten, Dense, LSTM, Input, concatenate, Conv1D
from keras.optimizers import Adam

from functools import lru_cache

class BasicGameModel(namedtuple('BasicGameModel', ['env'])):
    @lru_cache(maxsize=2)
    def model(self, newmodel=False):
        if os.path.isfile('modules/irwin/models/basicGame.h5') and not newmodel:
            logging.debug("model already exists, opening from file")
            return load_model('modules/irwin/models/basicGame.h5')
        logging.debug('model does not exist, building from scratch')

        moveStatsInput = Input(shape=(100, 6), dtype='float32', name='move_input')

        ### Conv Net Block of Siamese Network
        conv1 = Conv1D(filters=64, kernel_size=3, activation='relu')(moveStatsInput)
        dense1 = Dense(32, activation='relu')(conv1)
        conv2 = Conv1D(filters=64, kernel_size=5, activation='relu')(dense1)
        dense2 = Dense(32, activation='sigmoid')(conv2)
        conv3 = Conv1D(filters=64, kernel_size=10, activation='relu')(dense2)
        dense3 = Dense(16, activation='relu')(conv3)
        dense4 = Dense(8, activation='sigmoid')(dense3)

        f = Flatten()(dense4)
        dense5 = Dense(64, activation='relu')(f)
        convNetOutput = Dense(16, activation='sigmoid')(dense5)

        ### LSTM Block of Siamese Network
        mv1 = Dense(32, activation='relu')(moveStatsInput)
        d1 = Dropout(0.3)(mv1)
        mv2 = Dense(16, activation='relu')(d1)

        c1 = Conv1D(filters=64, kernel_size=5, name='conv1')(mv2)

        # analyse all the moves and come to a decision about the game
        l1 = LSTM(64, return_sequences=True)(c1)
        l2 = LSTM(32, return_sequences=True, activation='relu')(l1)

        c2 = Conv1D(filters=64, kernel_size=10, name='conv2')(l2)

        l3 = LSTM(32, return_sequences=True)(c2)
        l4 = LSTM(16, return_sequences=True, activation='relu', recurrent_activation='hard_sigmoid')(l3)
        l5 = LSTM(16, activation='sigmoid')(l4)

        mergeLSTMandConv = concatenate([l5, convNetOutput])
        denseOut1 = Dense(16, activation='sigmoid')(mergeLSTMandConv)
        mainOutput = Dense(1, activation='sigmoid', name='main_output')(denseOut1)

        model = Model(inputs=moveStatsInput, outputs=mainOutput)

        model.compile(optimizer=Adam(lr=0.0001),
            loss='binary_crossentropy',
            metrics=['accuracy'])
        return model

    def train(self, epochs, filtered=True, newmodel=False):
        # get player sample
        logging.debug("getting model")
        model = self.model(newmodel)
        logging.debug("getting dataset")
        batch = self.getTrainingDataset(filtered)

        logging.debug("training")
        logging.debug("Batch Info: Games: " + str(len(batch['data'])))

        model.fit(batch['data'], batch['labels'], epochs=epochs, batch_size=32, validation_split=0.2)

        self.saveModel(model)
        logging.debug("complete")

    def saveModel(self, model):
        logging.debug("saving model")
        model.save('modules/irwin/models/basicGame.h5')

    def getTrainingDataset(self, filtered):
        logging.debug("Getting players from DB")

        cheatTensors = []
        legitTensors = []

        logging.debug("Getting games from DB")
        if filtered:
            legits = self.env.playerDB.byEngine(False)
            for p in legits:
                legitTensors.extend([g.tensor(p.id) for g in self.env.gameDB.byUserId(p.id)])
            cheatGameActivations = self.env.gameBasicActivationDB.byEngineAndPrediction(True, 70)
            cheatGames = self.env.gameDB.byIds([ga.gameId for ga in cheatGameActivations])
            cheatTensors.extend([g.tensor(ga.userId) for g, ga in zip(cheatGames, cheatGameActivations)])
        else:
            cheats = self.env.playerDB.byEngine(True)
            legits = self.env.playerDB.byEngine(False)
            for p in legits + cheats:
                if p.engine:
                    cheatTensors.extend([g.tensor(p.id) for g in self.env.gameDB.byUserId(p.id)])
                else:
                    legitTensors.extend([g.tensor(p.id) for g in self.env.gameDB.byUserId(p.id)])

        cheatTensors = [t for t in cheatTensors if t is not None]
        legitTensors = [t for t in legitTensors if t is not None]

        shuffle(cheatTensors)
        shuffle(legitTensors)

        logging.debug("batching tensors")
        return self.createBatchAndLabels(cheatTensors, legitTensors)

    @staticmethod
    def createBatchAndLabels(cheatBatch, legitBatch):
        # group the dataset into batches by the length of the dataset, because numpy needs it that way
        mlen = min(len(cheatBatch), len(legitBatch))

        cheats = cheatBatch[:mlen]
        legits = legitBatch[:mlen]

        logging.debug("batch size " + str(len(cheats + legits)))

        labels = [1]*len(cheats) + [0]*len(legits)

        blz = list(zip(cheats+legits, labels))
        shuffle(blz)

        return {
            'data': np.array([t for t, l in blz]),
            'labels': np.array([l for t, l in blz])
        }