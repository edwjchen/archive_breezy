# breezy
Breezy


## Data collection script usage
```
python data_collection.py -r [path to repository to analyze]
```

NOTE: bug specification is hard coded into `data_collection.py` right now.

## Installing CPPCheck

Use the instructions given on their website at http://cppcheck.sourceforge.net/

As long as you can run
```bash
cppcheck
```
on your terminal, you should be set!

## Buggy Repos
Currently the repo found at https://github.com/yuzu-emu/yuzu is being tested for bugs. All you have to do to run data_collection.py is to clone the yuzu repo in the same level as the 'breezy' repo.
