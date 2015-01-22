[![Build
Status](https://travis-ci.org/tstone2077/gitshelve.svg?branch=develop)](https://travis-ci.org/tstone2077/gitshelve)
[![Coverage Status](https://coveralls.io/repos/tstone2077/gitshelve/badge.svg?branch=develop)](https://coveralls.io/r/tstone2077/gitshelve?branch=feature%2Fdevelop)

Originally branched from https://github.com/duplys/git-issues

gitshelve is very useful standalone code inside of the git-issues.  This
repo is to separate it out into its own project.  That being the case,
the following changes were made:

1. original history has been retained [by using git filter-branch and
a simple command
line](http://git.661346.n2.nabble.com/Remove-all-files-except-a-few-files-using-filter-branch-td7567155.html).
2. code has been updated to support python 2 and 3 (2.7 and 3.2 tested)
3. unit tests have been written to cover 93% of the code.

Please be sure to view the LICENSE file for copying, modifying, or
distributing.
