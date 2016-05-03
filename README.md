# ☢ F̩̖R͚̬̹̻̲ͅA̳͕̠͝N̠̥̬̳͔͇͞ͅK̤̟̳̮̬̩̙͘E̞̩̬̼͔̫N̙̳̥̲̥̬͎S̰̠̠̭̲E͖R͚͍̜V̱̮E̸R̝ ☢

## Introduction

frankenserver (technically, frankenserver's monster) is a fork of the [Google
App Engine SDK](https://code.google.com/p/googleappengine/) with modifications
required by Khan Academy. It is specifically targeted at the Python SDK running
on Mac OS X or Linux. Other App Engine runtimes and operating systems should
work normally but are not tested or supported.

frankenserver's biggest advantage over the vanilla SDK is in how it watches the
files in your app for changes. It does this much more efficiently by 1) using a
native [FSEvents](https://developer.apple.com/library/mac/documentation/Darwin/Reference/FSEvents_Ref/Reference/reference.html)-based
file watcher on Mac OS X and 2) respecting the skip_files directive in your
app.yaml.

## Installation

**For Khan Academy developers:** frankenserver is a subrepo of webapp so
there's nothing to install (assuming you've run `make deps`). Simply run
`make serve` to serve webapp using frankenserver.

**For others:** Just `git clone` this repository into a convenient location and
set up a symlink or shell alias for running `python python/dev_appserver.py`
with your desired dev_appserver.py flags. To enable the FSEvents-based file
watcher on Mac OS X you'll also need to run
`pip install -r requirements.txt` (*highly* recommended).

## Extra credit

- Set up Desmond's [Technicolor Yawn](https://github.com/dmnd/technicolor-yawn)
to give your request logs some color. (Khan Academy developers: `make serve`
will automatically use this if you have it installed.)

- Khan Academy developers: use
[multitail](http://www.vanheusden.com/multitail/) to interleave the logs from
frankenserver and kake, our build system, in a single terminal window.
(You can run `tail -f genfiles/kake-server.log` from your webapp directory to
get kake's log output.)

## Dealing with the upstream codebase

The github repo is typically behind the release tarballs, so we update
from upstream using the tarballs.

1. Visit https://cloud.google.com/appengine/downloads and download the
   latest zipfile.
2. Create a new branch: `git checkout master && git checkout -b <gae version>`
3. Replace the old code with the new: `rm -rf *; unzip <zipfile>`
4. If the zipfile toplevel is named `google_appengine`, do 
   `mv google_appengine python`
5. `git add -A .`
6. `git commit -am 'Pristine copy of <gae version>, without patches applied'`
7. (Now comes the hard part: cherry-picking the frankenserver changes
   from a previous branch.)
8. Run `git branch` to see what previous versions exist, then run
   `git log <previous version>` to see all the frankenserver changes.
   Stop when you get to the 'Pristine copy of <previous version>'
   log message (or something similar).  Note that commit.
9. Do `git log --format=%h --no-merges <commit>..<previous version>`.
   Alternately, if you're curious what these commits are, just do
   `git log --oneline --no-merges <commit>..<previous version>`.
   e.g. `git log --oneline --no-merges 526771777..1.9.28`
10. Starting from the bottom, and preferably one at a time, run
    `git cherry-pick <commit>`.  Resolve any conflicts you see.
11. Run `python/run_tests.py`.
