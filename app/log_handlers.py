
import os
import gzip
import shutil
import itertools
from logging.handlers import RotatingFileHandler


class RollingFileHandler(RotatingFileHandler):
	"""
	Makes logs infinite, creating a new file when the current one is above a
	certain size (given by the logging.conf). The resulting files are in
	ascending order.
	It ignores the backupCount parameter from RotatingFileHandler.
	"""
	# override
	def doRollover(self):
		if self.stream:
			self.stream.close()
			self.stream = None
		# my code starts here
		for i in itertools.count(1):
			next_name = "%s.%d" % (self.baseFilename, i)
			if not os.path.exists(next_name):
				self.rotate(self.baseFilename, next_name)
				break
		# my code ends here
		if not self.delay:
			self.stream = self._open()


class RollingGzipFileHandler(RotatingFileHandler):
	# override
	def doRollover(self):
		if self.stream:
			self.stream.close()
			self.stream = None
		# my code starts here
		for i in itertools.count(1):
			next_name = "%s.%d.gz" % (self.baseFilename, i)
			if not os.path.exists(next_name):
				with open(self.baseFilename, 'rb') as original_log:
					with gzip.open(next_name, 'wb') as gzipped_log:
						shutil.copyfileobj(original_log, gzipped_log)
				os.remove(self.baseFilename)
				break
		# my code ends here
		if not self.delay:
			self.stream = self._open()
