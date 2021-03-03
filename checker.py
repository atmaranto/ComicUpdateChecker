import sys, os, json, datetime, re, hashlib
from urllib.request import urlopen, Request

def BeautifulSoup(f):
	# Lazily load BeautifulSoup
	from bs4 import BeautifulSoup as _BeautifulSoup
	
	return _BeautifulSoup(f, 'lxml')

BUFFER_SIZE = 1024 * 1024
def md5sum(readable):
	md5 = hashlib.md5()
	
	while True:
		data = readable.read(BUFFER_SIZE)
		if not data: break
		
		md5.update(data)
	
	return md5.hexdigest()

timestamp_format = "%a, %d %b %Y %H:%M:%S %Z"
appdata = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
if not appdata and os.environ.get("HOME"): appdata = os.path.join(os.environ.get("HOME"), ".comicupdate")

if not appdata:
	print("Unable to find appplication data directory; exiting.", file=sys.stderr)
	sys.exit(1)

checker_dir = os.path.join(appdata, "ComicUpdateChecker")
if not os.path.exists(checker_dir):
	os.makedirs(checker_dir)

config_file = os.path.join(checker_dir, "config.json")

if not os.path.isfile(config_file):
	print("Warning: no config file at {0:}, nothing to do!".format(config_file), file=sys.stderr)
	sys.exit(0)
else:
	with open(config_file, "r", encoding="utf-8") as f:
		config = json.load(f)
	
	if not isinstance(config, dict):
		print("Invalid JSON in config file (must evaluate to a dict)", file=sys.stderr)
		sys.exit(1)
	
	for name, configuration in config.items():
		if not isinstance(configuration, dict):
			print("Invalid configuration item for key", name, file=sys.stderr)
			sys.exit(1)
		
		if not configuration.get("url"):
			print("Missing \"url\" attribute in configuration", name, file=sys.stderr)
			sys.exit(1)

data_file = os.path.join(checker_dir, "data.json")

if not os.path.isfile(data_file):
	data = {}
else:
	with open(data_file, "r", encoding="utf-8") as f:
		data = json.load(f)

class SoupHasher:
	def __init__(self, soup, criteria):
		self.soup = soup
		self.results = soup.find_all(criteria.get("name"), criteria.get("attrs"))[::-1]
		self._buf = b""
	
	def read(self, n):
		if not self._buf:
			if not self.results:
				return b""
			
			self._buf = self.results.pop(-1).prettify().encode('utf-8')
		
		to_return = self._buf[:n]
		self._buf = self._buf[n:]
		
		return to_return

new = []
for name, configuration in config.items():
	#print("Checking", name)
	
	if data.get(name, {}).get("last_modified"):
		headers = {
			"If-Modified-Since": data[name]["last_modified"]
		}
	else:
		headers = {}
	
	try:
		r = urlopen(Request(configuration["url"], headers=headers))
	except Exception as err:
		r = err
		print(name, "unmodified")
		continue
	else:
		last_modified = r.headers["Last-Modified"]
		
		if last_modified == None:
			# Server doesn't support last modified; we'll have to do it ourselves
			to_hash = r
			
			if configuration.get("criteria"):
				to_hash = SoupHasher(BeautifulSoup(r), configuration.get("criteria"))
			
			hexdigest = md5sum(to_hash)
			
			if data.get(name, {}).get("hash") != hexdigest:
				last_modified = datetime.datetime.now().strftime(timestamp_format)
				data.setdefault(name, {})["hash"] = hexdigest
				print("* {0:} modified (checked via hash)".format(name.upper()))
			else:
				print(name, "unmodified (checked via hash)")
		else:
			print("* {0:} modified {1:}".format(name.upper(), datetime.datetime.strptime(last_modified, timestamp_format)))
			data.setdefault(name, {})["last_modified"] = last_modified
	
with open(data_file, "w", encoding="utf-8") as f:
	json.dump(data, f, indent=4)

try:
	input("Press enter to exit.")
except EOFError: # Ignore errors that occur due to an already-closed stdin
	pass