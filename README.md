# BetterPonymotes-Cache

BetterPonymotes is an emote addon to serve the pony subreddits. It currently
supports Chrome (including other browsers that support Chrome extensions, like
Opera, Chromium, and Vivaldi), Firefox, Firefox Mobile, and Safari.

Its data is maintained as a set of files by the addon maintainer, and compiled
into compact representations for use by the addon at build time in the form of
a large, executable JS file. Its code is split between maintenance tools on
the backend (mostly Python) and JS that runs in the browser.

This repo acts as a server with its cached JSON file to provide necessary metadata for the app currently in planning. All unnecessary files have been removed. This repo is meant to be up to date by cherry-picking from the original repository.
