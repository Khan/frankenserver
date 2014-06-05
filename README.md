# ☢ F̩̖R͚̬̹̻̲ͅA̳͕̠͝N̠̥̬̳͔͇͞ͅK̤̟̳̮̬̩̙͘E̞̩̬̼͔̫N̙̳̥̲̥̬͎S̰̠̠̭̲E͖R͚͍̜V̱̮E̸R̝ ☢

## Introduction

frankenserver (technically, frankenserver's monster) is a fork of the [Google
App Engine SDK](https://code.google.com/p/googleappengine/) with modifications
required by Khan Academy. This repository is new and not yet up-to-date with
all of our patches, but it will eventually contain most of the changes from our
original [Homebrew formula](https://github.com/dylanvee/homebrew-gae_sdk) for
the SDK.

frankenserver is specifically targeted at the Python SDK running on Mac OS X or
Linux. Other App Engine runtimes and operating systems are not supported.

## Installation

For now, just `git clone` this repository into a convenient location and set
up a symlink or shell alias for running `python python/dev_appserver.py` with
your desired dev_appserver.py flags. Khan Academy developers can consult our
onboarding docs for more information.

If you are a Mac OS X user you may also use our original
[Homebrew formula](https://github.com/dylanvee/homebrew-gae_sdk) that inspired
this frankenserver. That formula is more up-to-date than this repository at the
moment, but eventually it will be deprecated in favor of a new formula that
installs frankenserver directly from this git svn mirror instead of applying
patchfiles to the SDK's release archive.

## Extra credit

- Set up Desmond's [Technicolor Yawn](https://github.com/dmnd/technicolor-yawn)
to give your request logs some color.

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

And the command to bring in upstream changes is `git svn fetch`.
