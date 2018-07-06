from default_imports import *

from modules.game.AnalysedGame import AnalysedGameBSONHandler

from modules.game.Env import Env

@validated
class Api(NamedTuple('Api', [
        ('env', Env)
    ])):
    @validated
	def insertAnalysedGames(self, analysedGamesBSON: Dict):
		try:
			analysedGames = [AnalysedGameBSONHandler.reads(g) for g in analysedGamesBSON]
			env.analysedGameDB.lazyWriteMany(analysedGames)
		except KeyError, ValueError:
			logging.warning('Malformed analysedGamesBSON: ' + str(analysedGamesBSON))