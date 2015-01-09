#!/usr/bin/env python
# coding: utf-8

# gitshelve.py, version 0.1
#
# by John Wiegley <johnw@newartisans.com>
#
# This file implements a Python shelve object that uses a branch within the
# current Git repository to store its data, plus a history of all changes to
# that data.  The usage is identical to shelve, with the exception that a
# repository directory or branch name must be specified, and that
# writeback=True is assumed.
#
# Example:
#
#   import gitshelve
#
#   data = gitshelve.open(branch = 'mydata', repository = '/tmp/foo')
#   data = gitshelve.open(branch = 'mydata')  # use current repo
#
#   data['foo/bar/git.c'] = "This is some sample data."
#
#   data.commit("Changes")
#   data.sync()                  # same as data.commit()
#
#   print data['foo/bar/git.c']
#
#   data.close()
#
# If you checkout the 'mydata' branch now, you'll see the file 'git.c' in the
# directory 'foo/bar'.  Running 'git log' will show the change you made.

import re
import os
from pipes import quote

try:
    from StringIO import StringIO
except:
    from io import StringIO

from subprocess import Popen, PIPE

######################################################################

# Utility function for calling out to Git (this script does not try to
# be a Git library, just an interface to the underlying commands).  It
# supports a 'restart' keyword, which will cause a Python function to
# be called on failure.  If that function returns True, the same
# command will be attempted again.  This can avoid costly checks to
# make sure a branch exists, for example, by simply failing on the
# first attempt to use it and then allowing the restart function to
# create it.


class GitError(Exception):
    def __init__(self, cmd, args, kwargs, stderr=None, returncode = 0):
        Exception.__init__(self)
        self.cmd = cmd
        self.args = args
        self.kwargs = kwargs
        self.stderr = stderr
        self.returncode = returncode

    def __str__(self):
        return self.__unicode__()

    def __unicode__(self):
        errorMsg = "Git command failed"
        if self.returncode != 0:
            errorMsg += "(%d)"%self.returncode
        errorMsg += ": git %s %s"%(
            self.cmd,' '.join(quote(s) for s in self.args))
        if self.stderr:
            errorMsg += " %s"%(self.stderr)
        return errorMsg

def __set_repo_environ(environ,repository):
    if repository is not None:
        git_dir = environ['GIT_DIR'] = repository
        if not os.path.isdir(git_dir):
            proc = Popen(('git', 'init'), env=environ,
                         stdout=PIPE, stderr=PIPE)
            if proc.wait() != 0:
                raise GitError('init', [], {}, proc.stderr.read())

def __set_worktree_environ(environ,worktree):
    if worktree is not None:
        environ['GIT_WORK_TREE'] = worktree
        if not os.path.isdir(worktree):
            os.makedirs(worktree)

def git(cmd, *args, **kwargs):
    stdin_mode = None
    if 'input' in kwargs:
        stdin_mode = PIPE

    environ = os.environ.copy()
    __set_repo_environ(environ,kwargs.get('repository'))
    __set_worktree_environ(environ, kwargs.get('worktree'))

    proc = Popen(('git', cmd) + args, env=environ,
                 stdin=stdin_mode,
                 stdout=PIPE,
                 stderr=PIPE)

    input = kwargs.get('input','')
    if isinstance(input, str):
        input = input.encode("utf-8")
    out, err = proc.communicate(input)

    returncode = proc.returncode
    restart = False
    ignore_errors = kwargs.get('ignore_errors',False)
    if returncode != 0 and not ignore_errors:
            raise GitError(cmd, args, kwargs, err, returncode)

    try:
        retval = str(out,'utf-8')
    except TypeError:
        retval = unicode(out)

    if 'keep_newline' not in kwargs:
        retval = retval[:-1]

    return retval


class gitbook:
    """Abstracts a reference to a data file within a Git repository.  It also
    maintains knowledge of whether the object has been modified or not."""
    def __init__(self, shelf, path, name=None):
        self.shelf = shelf
        self.path = path
        self.name = name
        self.data = None
        self.dirty = False

    def __repr__(self):
        return '<gitshelve.gitbook %s %s %s>' % \
                (self.path, self.name, self.dirty)

    def get_data(self):
        if self.data is None:
            if self.name is None:
                raise ValueError("name and data are both None")
            self.data = self.deserialize_data(self.shelf.get_blob(self.name))
        return self.data

    def set_data(self, data):
        if data != self.data:
            self.name = None
            self.data = data
            self.dirty = True

    def serialize_data(self, data):
        return data

    def deserialize_data(self, data):
        return data

    def change_comment(self):
        return None

    def __getstate__(self):
        odict = self.__dict__.copy()  # copy the dict since we change it
        del odict['dirty']            # remove dirty flag
        return odict

    def __setstate__(self, ndict):
        self.__dict__.update(ndict)   # update attributes
        self.dirty = False


class gitshelve(dict):
    """This class implements a Python "shelf" using a branch within a Git
    repository.  There is no "writeback" argument, meaning changes are only
    written upon calling close or sync.

    This implementation uses a dictionary of gitbook objects, since we don't
    really want to use Pickling within a Git repository (it's not friendly to
    other Git users, nor does it support merging)."""
    ls_tree_pat = \
            re.compile('((\d{6}) (tree|blob)) ([0-9a-f]{40})\t(start|(.+))$')

    head = None
    dirty = False
    objects = {}
    book_type = gitbook
    branch = 'master'
    repository = None
    keep_history = True

    def __init__(self, branch='master', repository=None,
                 keep_history=True, book_type=gitbook):
        self.branch = branch
        self.repository = repository
        self.keep_history = keep_history
        self.book_type = book_type
        self.init_data()
        dict.__init__(self)

    def init_data(self):
        self.head = None
        self.dirty = False
        self.objects = {}

    def git(self, *args, **kwargs):
        if self.repository:
            kwargs['repository'] = self.repository
        return git(*args, **kwargs)

    def current_head(self):
        return self.git('rev-parse', self.branch)

    def update_head(self, new_head):
        if self.head:
            self.git('update-ref', 'refs/heads/%s' % self.branch, new_head,
                     self.head)
        else:
            self.git('update-ref', 'refs/heads/%s' % self.branch, new_head)
        self.head = new_head

    def __parse_ls_tree_line(self,treep,perm,name,path):
        parts = path.split(os.sep)
        d = self.objects
        for part in parts:
            if not part in d:
                d[part] = {}
            d = d[part]

        if treep:
            d['__root__'] = name
        else:
            if perm == '100644':
                d['__book__'] = self.book_type(self, path, name)
            else:
                raise GitError('read_repository', [], {},
                       'Invalid mode for %s : 100644 required, %s found' \
                            % (path, perm))

    def read_repository(self):
        self.init_data()
        try:
            self.head = self.current_head()
        except:
            return

        ls_tree = self.git('ls-tree', '--full-tree','-r', '-t', '-z', 
                           self.head).split('\0')
        for line in ls_tree:
            match = self.ls_tree_pat.match(line)
            if not match:
                raise ValueError("ls-tree went insane: %s" % line)

            treep = match.group(1) == "040000 tree"
            perm = match.group(2)
            name = match.group(4)
            path = match.group(5)
            self.__parse_ls_tree_line(treep,perm,name,path)

    def open(cls, branch='master', repository=None,
             keep_history=True, book_type=gitbook):
        shelf = gitshelve(branch, repository, keep_history, book_type)
        shelf.read_repository()
        return shelf

    open = classmethod(open)

    def get_blob(self, name):
        return self.git('cat-file', 'blob', name, keep_newline=True)

    def hash_blob(self, data):
        return self.git('hash-object', '--stdin', input=data)

    def make_blob(self, data):
        return self.git('hash-object', '-w', '--stdin', input=data)

    def make_tree(self, objects):
        buf = StringIO()

        root = objects.get('__root__')

        for path in list(objects.keys()):
            if path == '__root__':
                continue

            obj = objects[path]
            if not isinstance(obj, dict):
                raise TypeError("objects['%s'] is not a dict"%path)

            if len(list(obj.keys())) == 1 and '__book__' in obj:
                book = obj['__book__']
                if book.dirty:
                    book.name = self.make_blob(book.serialize_data(book.data))
                    book.dirty = False
                    root = None
                buf.write("100644 blob %s\t%s\0" % (book.name, path))
            else:
                tree_root = None
                if '__root__' in obj:
                    tree_root = obj['__root__']

                tree_name = self.make_tree(obj)
                if tree_name != tree_root:
                    root = None

                buf.write("040000 tree %s\t%s\0" % (tree_name, path))

        if root is None:
            name = self.git('mktree', '-z', input=buf.getvalue())
            objects['__root__'] = name
            return name
        else:
            return root

    def make_commit(self, tree_name, comment):
        if not comment:
            comment = ""
        if self.head and self.keep_history:
            name = self.git('commit-tree', tree_name, '-p', self.head,
                            input=comment)
        else:
            name = self.git('commit-tree', tree_name, input=comment)

        self.update_head(name)
        return name

    def commit(self, comment=None):
        if not self.dirty:
            return self.head

        # Walk the objects now, creating and nesting trees until we end up
        # with a top-level tree.  We then create a commit out of this tree.
        tree = self.make_tree(self.objects)
        name = self.make_commit(tree, comment)

        self.dirty = False
        return name

    def sync(self):
        self.commit()

    def get_parent_ids(self):
        r = self.git('rev-list', '--parents', '--max-count=1', self.branch)
        return r.split()[1:]

    def close(self):
        if self.dirty:
            self.sync()
        del self.objects        # free it up right away

    def dump_objects(self, fd, indent=0, objects=None):
        if objects is None:
            objects = self.objects

        if '__root__' in objects and indent == 0:
            data = '%stree %s\n' % (" " * indent, objects['__root__'])
            data.encode('utf-8')
            fd.write('%stree %s\n' % (" " * indent, objects['__root__']))
            indent += 2

        keys = list(objects.keys())
        keys.sort()
        for key in keys:
            indent = self.processKeys(fd,indent,objects,key)

    def processKeys(self,fd,indent,objects,key):
        if key == '__root__':
            return indent
        if not isinstance(objects[key], dict):
            raise TypeError("objects['%s'] is not a dict"%key)

        if ('__book__' in objects[key]):
            book = objects[key]['__book__']
            if book.name:
                kind = 'blob ' + book.name
            else:
                kind = 'blob'
        else:
            if ('__root__' in objects[key]):
                kind = 'tree ' + objects[key]['__root__']
            else:
                kind = 'tree'

        fd.write('%s%s: %s\n' % (" " * indent, kind, key))

        if kind[:4] == 'tree':
            self.dump_objects(fd, indent + 2, objects[key])
        return indent

    def get_tree(self, path, make_dirs=False):
        parts = path.split(os.sep)
        d = self.objects
        for part in parts:
            if make_dirs and not (part in d):
                d[part] = {}
            d = d[part]
        return d

    def get(self, key):
        path = '%s/%s' % (key[:2], key[2:])
        d = None
        try:
            d = self.get_tree(path)
        except KeyError:
            raise KeyError(key)
        if not d or not ('__book__' in d):
            raise KeyError(key)
        return d['__book__'].get_data()

    def put(self, data):
        book = self.book_type(self, '__unknown__')
        book.data = data
        book.name = self.make_blob(book.serialize_data(book.data))
        book.dirty = False      # the blob was just written!
        book.path = '%s/%s' % (book.name[:2], book.name[2:])

        d = self.get_tree(book.path, make_dirs=True)
        d.clear()
        d['__book__'] = book
        self.dirty = True

        return book.name

    def __getitem__(self, path):
        d = None
        try:
            d = self.get_tree(path)
        except KeyError:
            raise KeyError(path)

        if d is not None and '__book__' in d:
            return d['__book__'].get_data()
        else:
            raise KeyError(path)

    def __setitem__(self, path, data):
        d = self.get_tree(path, make_dirs=True)
        if '__book__' not in d:
            d.clear()
            d['__book__'] = self.book_type(self, path)
        d['__book__'].set_data(data)
        self.dirty = True

    def prune_tree(self, objects, paths):
        if len(paths) > 1:
            left = self.prune_tree(objects[paths[0]], paths[1:])
            # do not delete if there's something left besides __root__ and
            # paths[0]
            has_root = '__root__' in objects[paths[0]]
            if left > 0 or len(objects[paths[0]]) > int(has_root):
                if '__root__' in objects:
                    del objects['__root__']
                for tree in objects:
                    if '__root__' in objects[tree]:
                        del objects[tree]['__root__']
                return 3
        l = len(objects[paths[0]])
        del objects[paths[0]]
        self.dirty = True
        return l - 1

    def __delitem__(self, path):
        try:
            self.prune_tree(self.objects, path.split(os.sep))
        except KeyError:
            raise KeyError(path)

    def __contains__(self, path):
        d = self.get_tree(path)
        return len(list(d.keys())) == 1 and ('__book__' in d)

    def walker(self, kind, objects, path=''):
        for item in list(objects.items()):
            if item[0] == '__root__':
                continue
            if not isinstance(item[1], dict):
                raise TypeError("item[1] is not a dict")

            if path:
                key = os.sep.join((path, item[0]))
            else:
                key = item[0]

            if len(list(item[1].keys())) == 1 and ('__book__' in item[1]):
                value = item[1]['__book__']
                if kind == 'keys':
                    yield key
                elif kind == 'values':
                    yield value
                else:
                    if kind != 'items':
                        raise ValueError("kind != keys, values, nor items")
                    yield (key, value)
            else:
                for obj in self.walker(kind, item[1], key):
                    yield obj

        raise StopIteration

    def __iter__(self):
        return self.iterkeys()

    def iteritems(self):
        return self.walker('items', self.objects)

    def items(self):
        i = []
        for items in self.iteritems():
            i.append(items)
        return i

    def iterkeys(self):
        return self.walker('keys', self.objects)

    def keys(self):
        k = []
        for key in self.iterkeys():
            k.append(key)
        return k

    def itervalues(self):
        return self.walker('values', self.objects)

    def values(self):
        v = []
        for value in self.itervalues():
            v.append(value)
        return v

    def __getstate__(self):
        self.sync()                   # synchronize before persisting
        odict = self.__dict__.copy()  # copy the dict since we change it
        del odict['dirty']            # remove dirty flag
        return odict

    def __setstate__(self, ndict):
        self.__dict__.update(ndict)  # update attributes
        self.dirty = False

        # If the HEAD reference is out of date, throw away all data and
        # rebuild it.
        if not self.head or self.head != self.current_head():
            self.read_repository()


def open(branch='master', repository=None, keep_history=True,
         book_type=gitbook):
    return gitshelve.open(branch, repository, keep_history, book_type)

# gitshelve.py ends here
