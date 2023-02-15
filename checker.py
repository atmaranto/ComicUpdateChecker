"""

checker.py -- Checks whether or not the specific pages have been updated since
              the last run of this program.

MIT License

Copyright (c) 2022 Anthony Maranto

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

"""

import sys, os, json, datetime, re, hashlib
import requests

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.192 Safari/537.36"
TIMESTAMP_FORMAT = "%a, %d %b %Y %H:%M:%S %Z"
READ_BUFFER_SIZE = 1024 * 1024 # 1MB, used for buffered md5

def BeautifulSoup(f):
    # Lazily load BeautifulSoup
    from bs4 import BeautifulSoup as _BeautifulSoup
    
    return _BeautifulSoup(f, 'lxml')

def md5sum(readable):
    md5 = hashlib.md5()
    
    while True:
        data = readable.read(READ_BUFFER_SIZE)
        if not data: break
        
        md5.update(data)
    
    return md5.hexdigest()


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

if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="A checking script to see if comics or similar occasionally-updated websites have updated")

    ap.add_argument("-c", "--only-show-changes", action="store_true", help="Only shows new comic updates", dest="only_show_changes")
    ap.add_argument("-n", "--dont-save-changes", action="store_true", help="Doesn't save update/hash data to the data file (ignored first run for any page)", dest="dont_save_changes")
    ap.add_argument("-b", "--break-on-error", action="store_true", help="Breaks whenever an error occurs, printing the full traceback", dest="break_on_error")
    ap.add_argument("-A", "--user-agent", default=None, help="Specifies the user agent that should be used when requesting the webpage")
    ap.add_argument("-v", "--verbose", action="store_true", help="Enables additional verbose through stderr", dest="verbose")

    args = ap.parse_args()
    
    def verbose(*v_args, **kwargs):
        """Displays a message to stderr if verbose is enabled"""
        if args.verbose:
            print(*v_args, file=sys.stderr, **kwargs)

    def fatal(*args, code=1, **kwargs):
        """Displays a message to stderr and exits with an error code"""
        print(*args, file=sys.stderr, **kwargs)
        sys.exit(code)
    
    # Locate OS-dependant configuration directory
    appdata = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    checker_dir = None
    if not appdata and os.environ.get("HOME"): # Walrus operator could improve efficiency... I'll wait until 3.8 is more widely-used
        checker_dir = os.path.join(os.environ.get("HOME"), ".comicupdate")
    elif appdata:
        checker_dir = os.path.join(appdata, "ComicUpdateChecker")

    if checker_dir is None:
        fatal("Unable to find appplication data directory (LOCALAPPDATA, APPDATA, and HOME not set); exiting.")
    
    if not os.path.exists(checker_dir):
        os.makedirs(checker_dir)

    config_file = os.path.join(checker_dir, "config.json")
    verbose("Checker config is at:", config_file)

    if not os.path.isfile(config_file):
        fatal("Warning: no config file at {}, nothing to do!".format(config_file))
    else:
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
        except json.decoder.JSONDecodeError as e:
            fatal("Encountered JSON error while decoding config file\n{}".format(e.args[0]))
        
        if not isinstance(config, dict):
            fatal("Invalid JSON in config file (must evaluate to a dict, instead found type {})".format(repr(type(config))))
        
        comic_config = config.get("comic_config", {})
        
        for name, configuration in comic_config.items():
            if not isinstance(configuration, dict):
                fatal("Invalid configuration item for key {}".format(name))
            
            if not configuration.get("url"):
                fatal("Missing \"url\" attribute in configuration {}".format(name))

    data_file = config.get("data_file")
    if data_file is not None:
        if not isinstance(data_file, str):
            fatal("\"data_file\" must be a string if specified!")
    else:
        data_file = os.path.join(checker_dir, "data.json") # Default path of the data file

    verbose("Checker data is at:", data_file)

    if not os.path.isfile(data_file):
        data = {}
        verbose("Creating new data file")
    else:
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.decoder.JSONDecodeError as e:
            fatal("Encountered JSON error while decoding data file\n{}".format(e.args[0]))
        
        verbose("Loaded existing data file at {}".format(data_file))
    
    # Used to determine if we should still save a config file if (somehow) we don't detect changes
    first_run_or_save = not args.dont_save_changes
    
    # We want our view of the page to match the user in their browser, so we set our user agent to theirs
    user_agent = args.user_agent
    if user_agent is None:
        config_user_agent = config.get("user_agent")
        if config_user_agent is None:
            user_agent = DEFAULT_USER_AGENT
        elif isinstance(config_user_agent, str):
            user_agent = config_user_agent
        else:
            fatal("Invalid typing for user agent in JSON file (expected string, found {})".format(repr(type(config_user_agent))))
    
    user_agent_headers = {"User-Agent": user_agent}
    
    new = []
    for name, configuration in comic_config.items():
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
            if getattr(r, 'status_code', None) == 304: # We use getattr here becuase this might be a URLError
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
            
            if last_modified is None or configuration.get("override-last-modified"):
                # Server doesn't support last modified; we'll have to do it ourselves
                to_hash = r.raw
                
                if configuration.get("criteria"):
                    to_hash = SoupHasher(BeautifulSoup(r.text), configuration.get("criteria"))
                
                hexdigest = md5sum(to_hash)
                
                if data_item.get("hash") != hexdigest:
                    last_modified = datetime.datetime.now().strftime(TIMESTAMP_FORMAT)
                    data.setdefault(name, {})["hash"] = hexdigest
                    print("* {0:} modified (checked via hash)".format(name.upper()))
                else:
                    if not args.only_show_changes:
                        print(name, "unmodified (checked via hash)")
            else:
                print("* {0:} modified {1:}".format(name.upper(), datetime.datetime.strptime(last_modified, TIMESTAMP_FORMAT)))
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
