# ComicUpdateChecker

 This is a simple, configurable script that uses BeautifulSoup and requests to check a certain number
 of webpages (or elements of webpages). It then compares those hashes of those
 webpages to determine if they've updated since the previous check, notifying
 the user if they have. I desinged it for use with webcomics, but really
 any page or page-segment should work.

## Requirements 

 This script requires `beautifulsoup4` and `requests`, which can be installed
 manually or via running the following command in this repository's directory.

```bash
python3 -m pip install -r requirements.txt
```

## Usage

### Configuration

 The configuration directory is located at `%LOCALAPPDATA%/ComicUpdateChecker`
 (falling back to `%APPDATA%` if `%LOCALAPPDATA%` is not found on Windows
 or at `~/.comicupdate` on Linux. If there is no `config.json` file found in that
 directory, the script will tell you where it's looking for it:

 ```bash
 python3 checker.py
Warning: no config file at C:\Users\username\AppData\Local\ComicUpdateChecker\config.json, nothing to do!
 ```

 The config.json file format is fairly simple:

```json
{
    "comic_config": {
        "xkcd": {
            "url": "https://xkcd.com/",
            "criteria": {
                "attrs": {
                    "id": "comic"
                }
            },
            "override-last-modified": true
        },
     
        "Freefall": {
            "url": "http://freefall.purrsia.com/default.htm"
        },
        
        "Order of the Stick": {
            "url": "https://www.giantitp.com/comics/oots.html"
        }
    }
}
```

The `"comic_config"` is the main config option. The key for each item in the
dict should be the page as you'd like it displayed. Each value in that should
be another dict, which should at *least* have the `"url"` property. This is
the url of the page you'd like to check for updates.

By default, the program will look for a "last-modified" header and use that
to determine if the page has changed. Unfortunately, lots of sites these days
send inaccurate last-modified headers (that either change too frequently or too
infrequently). To ignore the last-modified header, simply set
`"override-last-modified"` to `true` in the relevant page configuration.

When checking a page, the checker will download the page's HTML and compare
its md5 hash value to the previous one it has stored. Plenty of pages these
days have dynamic elements (advertisements, etc.) that will make the page
*constantly* look like it's been updated. Use the `"criteria"` option to
specify an HTML element to hash instead. If you're using this script like I
do, this will typically be the comic's `img` tag itself or the `div`
encompassing it.

Using the criteria, you can set `name`, which is the tag name (`div`, `img`,
etc.) and `attrs`, which are arbitrary attributes of the tag (commonly
`class` or `id` to disambiguate certain div tags from others). Some examples for
comics are above.

### Running the Script

 Once you've created the config file, you can simply run the script without
 arguments to check every page on its list. 

 ```bash
> python3 checker.py
* FREEFALL modified 2022-08-24 13:30:46
* ORDER OF THE STICK modified 2022-08-18 14:03:30
* XKCD modified (checked via hash)
Press enter to exit.
 ```

It stores the hash information in `data.json`, which is in the same
directory as `config.json`. You shouldn't need to deal with this file
directly, but here's an example anyways:

```json
{
    "Freefall": {
        "last_error": false,
        "last_modified": "Wed, 24 Aug 2022 1:00:00 GMT"
    },
    "Order of the Stick": {
        "last_error": false,
        "last_modified": "Thu, 18 Aug 2022 2:30:00 GMT"
    },
    "xkcd": {
        "hash": "00112233445566778899aabbccddeeff"
    }
}
```

 If you run it again, you'll see there are now no new updates (unless one
 of your pages happened to update in the time it took you to read this!).

```bash
> python3 checker.py
Freefall unmodified (checked via hash)
Order of the Stick unmodified (checked via hash)
xkcd unmodified (checked via hash)
Press enter to exit.
```

### Command-line options



 ```bash
> python3 checker.py --help
usage: checker.py [-h] [-c] [-n] [-b] [-A USER_AGENT] [-v]

A checking script to see if comics or similar occasionally-updated websites have updated

optional arguments:
  -h, --help            show this help message and exit
  -c, --only-show-changes
                        Only shows new comic updates
  -n, --dont-save-changes
                        Doesn't save update/hash data to the data file (ignored first run for any page)
  -b, --break-on-error  Breaks whenever an error occurs, printing the full traceback
  -A USER_AGENT, --user-agent USER_AGENT
                        Specifies the user agent that should be used when requesting the webpage
  -v, --verbose         Enables additional verbose through stderr
 ```

## Cron Configuration

 One thing I like to do is have a the set of updated pages displayed when
 I log into a new session on my Linux machine. To achieve this, I did two
 things:

 First, I updated my crontab. Type `crontab -e` and create a new line at the
 end of the file containing the following:

 ```
 1 * * * * (/usr/local/bin/python3 /path/to/your/checker.py --only-show-changes >> /home/YOUR_USERNAME/.comicupdate/lastrun.txt)
 ```
 
 Here, I've set the script to automatically run once on the
 first minute of every hour of every day, etc. (essentially, it will run
 this script once an hour).

 If you're unfamiliar with the environment cron jobs run in, you may need
 to make sure they have access to your Python installation.

 The `--only-show-changes` option ensures that we aren't going to be
 spammed with page "updates" that are really just notifications.
 
 Next, we can alter our `~/.bashrc` to display the updated page information
 that we collect in `lastrun.txt`, removing it whenever we display it. Since
 I use `tmux`, I've added a simple statement to disable it whenever we're
 in a `tmux` pane.

```bash
if ! test $TMUX; then
    cat ~/.comicupdate/ComicUpdateChecker/lastrun.txt 2>/dev/null; rm ~/.comicupdate/lastrun.txt 2>/dev/null
fi
```
 
 Now, every time you log in, you'll be ~~spammed~~ greeted with information
 about which of those websites you follow were updated!

~~Who needs RSS?~~
