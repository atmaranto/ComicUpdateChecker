import argparse

ap = argparse.ArgumentParser(description="A checking script to see if comics or similar occasionally-updated websites have updated")

ap.add_argument("--only-show-changes", action="store_true", help="Only shows new comic updates", dest="only_show_changes")
ap.add_argument("--dont-save-changes", action="store_true", help="Doesn't save update/hash data to the data file (ignored first run for any comic)", dest="dont_save_changes")
ap.add_argument("--break-on-error", action="store_true", help="Breaks whenever an error occurs, printing the full traceback", dest="break_on_error")
ap.add_argument("--verbose", action="store_true", help="Enables additional verbose through stderr", dest="verbose")

args = ap.parse_args()

import sys, os, json, datetime, re, hashlib
import requests

def verbose(*v_args, **kwargs):
	if args.verbose:
		print(*v_args, file=sys.stderr, **kwargs)

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
verbose("Checker config is at:", config_file)

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
verbose("Checker data is at:", data_file)

if not os.path.isfile(data_file):
	data = {}
	verbose("Creating new data file")
else:
	with open(data_file, "r", encoding="utf-8") as f:
		data = json.load(f)
	verbose("Creating new data file")

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

first_run_or_save = not args.dont_save_changes

user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.192 Safari/537.36"

user_agent_headers = {"User-Agent": user_agent}

new = []
for name, configuration in config.items():
	verbose("Checking", name)
	
	data_item = data.get(name)
	if not data_item:
		first_run_or_save = True
		data_item = {}
	
	if data_item.get("last_modified") and not configuration.get("override-last-modified"):
		headers = {
			"If-Modified-Since": data[name]["last_modified"]
		}
	else:
		headers = {}
	
	headers.update(user_agent_headers)
	error = None
	r = None
	
	try:
		verbose("Sending request to", configuration["url"])
		r = requests.get(configuration["url"], headers=headers)
	except Exception as err:
		verbose("Got exception " + r.__class__.__name__ + ": code " + str(getattr(r, "code", "None")) + "")
		error = err
	
	if error is not None or not r.ok:
		if getattr(r, 'status_code', None) == 304:
			if not args.only_show_changes:
				print(name, "unmodified (error)")
			
			continue
		else:
			if args.break_on_error and error is not None:
				raise error from None
			
			last_error = data.get("name", {}).get("last_error")
			data.setdefault(name, {})["last_error"] = True
			if args.only_show_changes and last_error:
				continue
			
			print("Failed to fetch", configuration["url"] + ":", getattr(r or error, "reason", None) or getattr(error, "args", None))
	else:
		last_modified = r.headers.get("Last-Modified", None)
		
		if last_modified == None or configuration.get("override-last-modified"):
			# Server doesn't support last modified; we'll have to do it ourselves
			to_hash = r.raw
			
			if configuration.get("criteria"):
				to_hash = SoupHasher(BeautifulSoup(r.text), configuration.get("criteria"))
			
			hexdigest = md5sum(to_hash)
			
			if data_item.get("hash") != hexdigest:
				last_modified = datetime.datetime.now().strftime(timestamp_format)
				data.setdefault(name, {})["hash"] = hexdigest
				print("* {0:} modified (checked via hash)".format(name.upper()))
			else:
				if not args.only_show_changes:
					print(name, "unmodified (checked via hash)")
		else:
			print("* {0:} modified {1:}".format(name.upper(), datetime.datetime.strptime(last_modified, timestamp_format)))
			data.setdefault(name, {})["last_error"] = False
			data[name]["last_modified"] = last_modified

if first_run_or_save:
	with open(data_file, "w", encoding="utf-8") as f:
		json.dump(data, f, indent=4)
	verbose("Saved data to", data_file)
else:
	verbose("first_run_or_save is False -- not saving")

if os.isatty(sys.stdin.fileno()) and os.isatty(sys.stdout.fileno()):
	try:
		input("Press enter to exit.")
	except EOFError: # Ignore errors that occur due to an already-closed stdin
		pass