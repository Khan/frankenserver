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

1. [Install `gcloud`](https://cloud.google.com/sdk/) (if you've run
   khan-dotfiles this will not be necessary), plus the relevant components:
   `gcloud components install app-engine-python app-engine-python-extras`
2. Find your gcloud install (normally `~/google-cloud-sdk`, or
   `~/khan/devtools/google-cloud-sdk` if you used khan-dotfiles for step 1);
   we're going to want to grab `platform/google_appengine` from within it.
3. Create a new branch: `git checkout master && git checkout -b <gae version>`
4. Replace the old code with the new:
   `rm -rf python ; cp -R ~/path/to/platform/google_appengine python`
5. Sadly, upstream no longer sets the right file permissions (because gcloud
   has its own binary wrappers), so revert all the permissions changes with
   `git diff -p -R | grep -E "^(diff|(old|new) mode)" | git apply`
6. `git add -A .`
7. `git commit -am 'Pristine copy of <gae version>, without patches applied'`
   (You can find the version on the release notes page:
   https://cloud.google.com/appengine/docs/standard/python/release-notes.)
8. (Now comes the hard part: cherry-picking the frankenserver changes
   from a previous branch.)
9. Run `git log` to see all the frankenserver changes; stop when you get to the
   'Pristine copy of <previous version>' log message (or something similar).
   Note that commit.
10. Do `git log --format=%h --no-merges <commit>..HEAD^`.
    Alternately, if you're curious what these commits are, just do
    `git log --oneline --no-merges <commit>..HEAD^`.
    e.g. `git log --oneline --no-merges 526771777..HEAD^`
11. Run `git cherry-pick <commit>..HEAD^`.  (Or, especially in case of
    conflicts, it may be easier to cherry-pick each commit one at a time.)
12. Run `python/run_tests.py`.  Or, since it may not actually run successfully,
    just do whatever testing seems reasonable -- run a few e2e tests against
    your dev server; load some pages; and test anything else you think suspect.
    For example, as of Feb 2019, I ran the following (the tests are somewhat
    arbitrary):
    ```
    virtualenv ~/.virtualenv/frankenserver -p python2  # create fresh venv
    source ~/.virtualenv/frankenserver/bin/activate
    pip install mock
    PYTHONPATH=. ./run_tests.py google.appengine.tools.devappserver2.{devappserver2_test,inotify_file_watcher_test,python.runtime.runtime_test}
    ```
    plus I ran some (arbitrary) e2e tests from webapp as a more end-to-end
    test of the dev server:
    ```
    tools/runtests.py --max-size=large coaches/end_to_end/coach_invitations_e2etest.py assignments/end_to_end/auto_assign_e2etest.py
    ```
