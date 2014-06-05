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
there's nothing to install. Simply run `make serve` to serve webapp using
frankenserver.

**For others:** Just `git clone` this repository into a convenient location and
set up a symlink or shell alias for running `python python/dev_appserver.py`
with your desired dev_appserver.py flags. To enable the FSEvents-based file
watcher on Mac OS X you'll also need to run
`pip install pyobjc-framework-FSEvents` (highly recommended).

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

This repository is a
[git-svn](https://www.kernel.org/pub/software/scm/git/docs/git-svn.html) mirror
of the [official SDK](https://code.google.com/p/googleappengine/). We have
configured the mirror to skip the java/ directory because it contains large
build artifacts that GitHub won't accept and are unnecessary for our needs. The
command to set up the mirror was:

```
git svn clone --stdlayout --ignore-paths="^trunk/java" http://googleappengine.googlecode.com/svn/ frankenserver
```

and the command to bring in upstream changes is `git svn fetch`.
