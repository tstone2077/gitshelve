# -*- coding: utf-8 -*-

import os
import re
import shutil
import sys
import tempfile
import unittest

try:
    from StringIO import StringIO
except:
    from io import StringIO

import gitshelve

SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))

class TestGitShelve(unittest.TestCase):
    def __init__(self,*args,**kwargs):
        unittest.TestCase.__init__(self,*args,**kwargs)
        try:
            self.assertRegex
        except AttributeError:
            self.assertRegex = self.assertRegexpMatches
    def __add_file_to_repo(self,name,type='file'):
        rootDir = self.gitDir
        if type == 'dir':
            rootDir = os.path.join(self.gitDir,name)
            os.makedirs(rootDir)
            name = '.empty'

        filename = os.path.join(rootDir,name)
        with open(filename,'w') as f:
            f.write('temp')
        stream = os.popen('git add %s'%filename)
        out = stream.read()
        stream.close()
        self.assertEqual('',out)
        stream = os.popen('git commit -m temp')
        out = stream.read()
        stream.close()
        commitRE = re.compile('.* ([0-9a-f]{7}).*? temp')
        self.assertIn('1 file changed, 1 insertion',out)
        return commitRE.search(out).group(1)
        
    def __use_new_repo(self):
        self.gitDir = tempfile.mkdtemp()
        self.lastCWD = os.getcwd()
        os.chdir(self.gitDir)
        stream = os.popen('git init')
        self.assertIn("Initialized empty Git repository in",stream.read())
        stream.close()

    def __cleanup_repo(self):
        """Delete the git repository"""
        os.chdir(self.lastCWD)
        shutil.rmtree(self.gitDir)
        self.stream.close()

    def setUp(self):
        """Create a new git repository, cd to it, and create the initial 
           commit"""
        self.__use_new_repo()
        #add a file to our repository
        self.firstCommit = self.__add_file_to_repo('file')
        self.stream = StringIO()
        self.gitConfigFile = os.path.join(os.environ['HOME'],'.gitconfig')
        #REVISIT:  This sucks! In order to force git init to fail, I have to 
        #change the user's ~/.gitconfig file.  That means if the unit tests
        #are aborted mid way through, the configuration can be lost.  There
        #needs to be a better way to make git init fail.
        with open(self.gitConfigFile) as f:
            self.gitConfig = f.read()

    def tearDown(self):
        self.__cleanup_repo()
        #make sure the user's git config file is the way it was before we found
        #it
        with open(self.gitConfigFile,'w') as f:
            f.write(self.gitConfig)

    def testGitError(self):
        cmd = 'branch'
        args = ['-D','test']
        kwargs = {}
        stderr = None
        returncode = 1
        e = gitshelve.GitError(cmd,args,kwargs,stderr,returncode)
        self.assertEqual(str(e),"Git command failed(1): git branch -D test")

        cmd = 'branch'
        args = ['-D','test']
        kwargs = {}
        stderr = "No branch for you"
        returncode = 1
        e = gitshelve.GitError(cmd,args,kwargs,stderr,returncode)
        self.assertEqual(str(e),"Git command failed(1): git branch -D test No"
                                " branch for you")
    def testGit(self):
        #run with verbose turned on
        gitshelve.verbose = True
        with NoStdStreams():
            self.assertEqual(gitshelve.git('branch','-a'),"* master")
            tree = gitshelve.git('write-tree')

        #test with input in kwargs
        stdIn = 'first commit'
        result = ""
        with NoStdStreams():
            result = gitshelve.git('commit-tree',tree,input = stdIn)

        self.assertRegex(result,'[0-9a-f]{40}')

        #from now on, run with verbose turned off
        gitshelve.verbose = False

        #test with repository in kwargs
        #-----repo exists
        rootRepoName = tempfile.mkdtemp()
        with self.assertRaises(gitshelve.GitError):
            gitshelve.git('ls-tree',repository = rootRepoName)
        #-----repo does not exist
        #----------first, cause git init to fail
        repoName = os.path.join(rootRepoName,"nonExistentRepo")
        with open(self.gitConfigFile,'w') as f:
            f.write("[push]\n\tdefault = trash")
        with self.assertRaises(gitshelve.GitError):
            gitshelve.git('write-tree',repository = repoName)
        shutil.rmtree(repoName)
        #----------fix config so git init won't fail
        with open(self.gitConfigFile,'w') as f:
            f.write(self.gitConfig)
        tree = gitshelve.git('write-tree',repository = repoName)
        self.assertRegex(tree,'[0-9a-f]{40}')
        cwdTree = gitshelve.git('ls-tree',tree)
        self.assertEqual('',cwdTree)
        shutil.rmtree(rootRepoName)

        #test with worktree in kwargs
        #-----repo exists
        rootRepoName = tempfile.mkdtemp()
        out = gitshelve.git('checkout','master', worktree = rootRepoName)
        self.assertEqual('D\tfile',out)
        #-----repo does not exist

        repoName = os.path.join(rootRepoName,'nonExistentRepo')
        out = gitshelve.git('checkout','master', worktree = repoName, keep_newline = True)
        self.assertEqual('D\tfile\n',out)
        shutil.rmtree(rootRepoName)

    def testGitbook(self):
        lsTreeRE = re.compile('(\d{6}) (tree|blob) ([0-9a-f]{40})\t(start|(.+))$')
        tree = gitshelve.git('ls-tree','--full-tree','-r', '-t','master')
        name = lsTreeRE.match(tree).group(3)
        shelf = gitshelve.gitshelve()
        b = gitshelve.gitbook(shelf, self.gitDir, name=name)
        self.assertEqual(repr(b),
                         '<gitshelve.gitbook %s %s False>'%(self.gitDir,name))
        data = 'temp'
        self.assertEqual(data,b.get_data())
        b.data = None
        b.name = None
        with self.assertRaises(ValueError):
            b.get_data()
        b.set_data(data)
        self.assertEqual(data,b.get_data())
        self.assertEqual(data,b.serialize_data(data))
        self.assertEqual(data,b.deserialize_data(data))
        newData = 'text'
        self.assertEqual(None,b.set_data(newData))
        self.assertEqual(None,b.change_comment())
        b.__setstate__({'data': 'something'})
        self.assertEqual(b.__getstate__(),{'shelf': {}, 'path': self.gitDir,
                                           'data': 'something', 'name': None})
    #----gitshelve tests-------
    def testGitshelveInit(self):
        s = gitshelve.gitshelve()
        s.close()

    def testGitshelveGit(self):
        s = gitshelve.gitshelve()
        out = s.git('ls-tree','--full-tree','-r','-t','master')
        expectedOut = '100644 blob 3602361dafeea2cbec159128f5166a8428c0795c' + \
                      '\tfile'
        self.assertEqual(expectedOut,out)
        s.repository = os.path.join(self.gitDir,".git")
        out = s.git('ls-tree','--full-tree','-r','-t','master')
        self.assertEqual(expectedOut,out)
        s.close()

    def testGitshelveCurrentHead(self):
        s = gitshelve.gitshelve()
        text = s.current_head()
        self.assertRegex(text,self.firstCommit)
        s.close()

    def testGitshelveUpdateHead(self):
        s = gitshelve.gitshelve()
        #TODO: Figure out how to test this
        s.close()

    def testGitshelveReadRepository(self):
        s = gitshelve.gitshelve()
        s.read_repository()
        #TODO: some verification that the repo was read

        #test using an empty repository.  This should return None.
        self.__cleanup_repo()
        self.__use_new_repo()
        self.assertEqual(None,s.read_repository())

        #test using a repository with at least one directory
        self.__add_file_to_repo('newDir',type='dir')
        s.read_repository()
        #TODO: some verification that the repo was read
        s.close()

    def testGitshelveHashBlob(self):
        data = 'this is some data'
        s = gitshelve.gitshelve()
        self.assertEqual('82fa9daba4cab515726fff892362b942dc01d625',
                         s.hash_blob(data))
        s.close()

    def testGitshelveMakeBlob(self):
        data = 'this is some data'
        s = gitshelve.gitshelve()
        self.assertEqual('82fa9daba4cab515726fff892362b942dc01d625',
                         s.make_blob(data))
        s.close()

    def testGitshelveMakeTree(self):
        #TODO:This test is very clumsy.  Work can be done to build a meaningful
        #tree
        data = 'this is some data'
        s = gitshelve.gitshelve()
        name = s.make_blob(data)
        objects = {}
        objects['__root__'] = ''
        objects['file'] = ''
        with self.assertRaises(TypeError):
            s.make_tree(objects)

        b = gitshelve.gitbook(s, self.gitDir, name=name)
        b.dirty = True
        objects['file'] = {'__book__':b}
        tree = s.make_tree(objects)
        objects[tree] = {'file':{'__book__':b}}
        newTree = s.make_tree(objects)
        s.close()

    def testGitshelveMakeCommit(self):
        data = 'this is some data'
        s = gitshelve.gitshelve()
        name = s.make_blob(data)
        objects = {}
        b = gitshelve.gitbook(s, self.gitDir, name=name)
        b.dirty = True
        objects['file'] = {'__book__':b}
        buf = StringIO()
        tree = s.make_tree(objects)
        comment = 'tree'
        s.make_commit(tree, comment)
        s.make_commit(tree, None)
        s.close()

    def testGitshelveCommit(self):
        s = gitshelve.gitshelve()
        newHead = s.commit()
        self.assertEqual(newHead,None)
        self.assertEqual(newHead,s.commit())

        s.dirty = True
        newHead = s.commit()
        s.close()

    def testGitshelveSync(self):
        s = gitshelve.gitshelve()
        s.sync()
        s.close()

    def testGitshelveGetParentIds(self):
        #TODO: figure out more meaningful tests for this
        s = gitshelve.gitshelve()
        self.assertEqual(s.get_parent_ids(),[])
        s.close()

    def testGitshelveClose(self):
        s = gitshelve.gitshelve()
        s.close()
        s = gitshelve.gitshelve()
        s['a']='a'
        s.close()

    def testGitshelveDumpObjects(self):
        s = gitshelve.gitshelve()
        b = gitshelve.gitbook(s, self.gitDir, name='master')
        buf = StringIO()
        s.dump_objects(buf)
        self.assertEqual("",buf.getvalue())

        s['temp'] = 'a'
        s.dump_objects(buf)
        self.assertEqual("blob: temp\n",buf.getvalue())
        buf = StringIO()

        objects = {}
        #TODO: Fix this dictionary to store the correct values
        objects['__root__'] = {'temp':'a'}
        s.dump_objects(buf,0,objects)
        self.assertEqual("tree {'temp': 'a'}\n",buf.getvalue())
        buf = StringIO()

        objects['file'] = 'temp'
        with self.assertRaises(TypeError):
            s.dump_objects(buf,0,objects)
        buf = StringIO()

        objects['file'] = {'__root__':'someTree'}
        s.dump_objects(buf,0,objects)
        expectedOutput =  "tree {'temp': 'a'}\n  tree someTree: file\n"
        self.assertEqual(expectedOutput,buf.getvalue())
        buf = StringIO()

        objects['file'] = {'file':{'__book__':b}}
        s.dump_objects(buf,0,objects)
        expectedOutput = "tree {'temp': 'a'}\n" +\
                         "  tree: file\n" +\
                         "    blob master: file\n"
        self.assertEqual(expectedOutput,buf.getvalue())
        buf = StringIO()

        objects['file'] = {'__book__':b}
        s.dump_objects(buf,0,objects)
        expectedOutput = "tree {'temp': 'a'}\n  blob master: file\n"
        self.assertEqual(expectedOutput,buf.getvalue())
        s.close()

    def testGitshelveGetTree(self):
        s = gitshelve.gitshelve()
        with self.assertRaises(KeyError):
            s.get_tree('temp', make_dirs=False)
        s['a/b'] = 'c'
        self.assertIn('b',s.get_tree('a'))
        s.close()

    def testGitshelveGetAndSetItem(self):
        s = gitshelve.gitshelve()
        with self.assertRaises(KeyError):
            s['temp']
        s['temp'] = 'a'
        self.assertEqual('a',s['temp'])
        s.close()

    def testGitshelvePruneTree(self):
        s = gitshelve.gitshelve()
        s['temp/temp'] = 'temp'
        s['temp/temp2'] = 'temp'
        b = gitshelve.gitbook(s, self.gitDir, name='master')
        s.prune_tree(s.objects,['temp','temp2'])
        s.close()

    def testGitshelveDelItem(self):
        s = gitshelve.gitshelve()
        s['temp/temp'] = 'temp'
        s['temp/temp2'] = 'temp'
        del s['temp']
        with self.assertRaises(KeyError):
            del s['temp2']
        s.close()

    def testGitshelveContains(self):
        s = gitshelve.gitshelve()
        s['temp/temp'] = 'temp'
        self.assertEqual(True,'temp/temp' in s)
        s.close()

    def testGitshelveWalker(self):
        #TODO: Figure out how to test this better
        pass

    def testGitshelveItems(self):
        s = gitshelve.gitshelve()
        s['temp'] = 'temp'
        s['temp2'] = 'temp'
        s['temp3'] = 'temp'
        i = s.items()
        s.close()
        
    def testGitshelveValues(self):
        s = gitshelve.gitshelve()
        s['temp'] = 'temp'
        s['temp2'] = 'temp'
        s['temp3'] = 'temp'
        v = s.values()
        s.close()

    def testGitshelveKeys(self):
        s = gitshelve.gitshelve()
        s['temp'] = 'temp'
        s['temp2'] = 'temp'
        s['temp3'] = 'temp'
        k = s.keys()
        s.close()

    def testGitshelveGetAndSetState(self):
        import pickle
        s = gitshelve.gitshelve()
        s['temp'] = 'temp'
        s['temp2'] = 'temp'
        s['temp3'] = 'temp'
        sStr = pickle.dumps(s)
        s = pickle.loads(sStr)
        #change the head
        s['temp4'] = 'temp'
        s.commit()
        s = pickle.loads(sStr)
        s.close()

    def testOpen(self):
        s = gitshelve.open()

    def testBasicInsertion(self):
        shelf = gitshelve.open('test')
        text = "Hello, this is a test\n"
        shelf['foo/bar/baz.c'] = text

        self.assertEqual(text, shelf['foo/bar/baz.c'])

        def foo1(shelf):
            return shelf['foo/bar']
        self.assertRaises(KeyError, foo1, shelf)

        del shelf

    def testBasicDeletion(self):
        shelf = gitshelve.open('test')
        text = "Hello, this is a test\n"
        shelf['foo/bar/baz.c'] = text
        del shelf['foo/bar/baz.c']

        def foo2(shelf):
            return shelf['foo/bar/baz.c']
        self.assertRaises(KeyError, foo2, shelf)

        shelf['foo/bar/baz.c'] = text
        del shelf['foo/bar']

        def foo4(shelf):
            return shelf['foo/bar/baz.c']
        self.assertRaises(KeyError, foo4, shelf)

        del shelf

    def testInsertion(self):
        shelf = gitshelve.open('test')
        text = "Hello, this is a test\n"
        shelf['foo/bar/baz.c'] = text

        buf = StringIO()
        shelf.dump_objects(buf)

        self.assertEqual(buf.getvalue(), """tree: foo
  tree: bar
    blob: baz.c
""")

        hash1 = shelf.commit('first\n')
        hash2 = shelf.commit('second\n')
        self.assertEqual(hash1, hash2)

        buf = StringIO()
        shelf.dump_objects(buf)

        self.assertEqual("""tree ca37be3e31987d8ece35001301c0b8f1fccbb888
  tree 95b790693f3b5934c63d10b8b007e4758f6134a9: foo
    tree c03cdd65fa74c272bed2e9a48e3ed19402576e19: bar
      blob ea93d5cc5f34e13d2a55a5866b75e2c58993d253: baz.c
""", buf.getvalue())

        hash3 = shelf.current_head()
        self.assertEqual(hash1, hash3)

        commit = gitshelve.git('cat-file', 'commit', 'test',
                               keep_newline = True)
        self.assertTrue(re.search('first\n$', commit))

        data = gitshelve.git('cat-file', 'blob', 'test:foo/bar/baz.c',
                             keep_newline = True)
        self.assertEqual(text, data)

        del shelf
        shelf = gitshelve.open('test')

        self.assertEqual("""tree ca37be3e31987d8ece35001301c0b8f1fccbb888
  tree 95b790693f3b5934c63d10b8b007e4758f6134a9: foo
    tree c03cdd65fa74c272bed2e9a48e3ed19402576e19: bar
      blob ea93d5cc5f34e13d2a55a5866b75e2c58993d253: baz.c
""", buf.getvalue())

        self.assertEqual(text, shelf['foo/bar/baz.c'])
        del shelf

    def testIterator(self):
        shelf = gitshelve.open('test')
        text = "Hello, this is a test\n"
        shelf['foo/bar/baz1.c'] = text
        shelf['alpha/beta/baz2.c'] = text
        shelf['apple/orange/baz3.c'] = text

        buf = StringIO()
        keys = list(shelf.keys())
        keys.sort()
        for path in keys:
            try:
                buf.write("path: (%s)\n" % path)
            except TypeError:
                buf.write(unicode("path: (%s)\n" % path))

        self.assertEqual("""path: (alpha/beta/baz2.c)
path: (apple/orange/baz3.c)
path: (foo/bar/baz1.c)
""", buf.getvalue())

    def testVersioning(self):
        shelf = gitshelve.open('test')
        text = "Hello, this is a test\n"
        shelf['foo/bar/baz1.c'] = text
        shelf.sync()

        buf = StringIO()
        shelf.dump_objects(buf)
        self.assertEqual("""tree 073629aeb0ef56a50a6cfcaf56da9b8393604b56
  tree ce9d91f2da4ab3aa920cd5763be48b9aef76f999: foo
    tree 2e626f2ae629ea77618e84e79e1bfae1c473452e: bar
      blob ea93d5cc5f34e13d2a55a5866b75e2c58993d253: baz1.c
""", buf.getvalue())

        text = "Hello, this is a change\n"
        shelf['foo/bar/baz1.c'] = text
        shelf['foo/bar/baz2.c'] = text
        shelf.sync()

        buf = StringIO()
        shelf.dump_objects(buf)
        self.assertEqual("""tree c7c6fd4368460c645d0953349d5577d32f46115a
  tree 3936ea8daffe9eef0451b43205d6530374f8ffa3: foo
    tree 8f7bfca3bc33c93fb1a878bc79c2bb93d8f41730: bar
      blob fb54a7573d864d4b57ffcc8af37e7565e2ba4608: baz1.c
      blob fb54a7573d864d4b57ffcc8af37e7565e2ba4608: baz2.c
""", buf.getvalue())

        del shelf

        shelf = gitshelve.open('test')

        buf = StringIO()
        shelf.dump_objects(buf)
        self.assertEqual("""tree 3936ea8daffe9eef0451b43205d6530374f8ffa3: foo
  tree 8f7bfca3bc33c93fb1a878bc79c2bb93d8f41730: bar
    blob fb54a7573d864d4b57ffcc8af37e7565e2ba4608: baz1.c
    blob fb54a7573d864d4b57ffcc8af37e7565e2ba4608: baz2.c
""", buf.getvalue())

        self.assertEqual(text, shelf['foo/bar/baz1.c'])
        self.assertEqual(text, shelf['foo/bar/baz2.c'])

        log = gitshelve.git('log', 'test', keep_newline = True)

        self.assertTrue(re.match("""commit [0-9a-f]{40}
Author: .+
Date:   .+

commit [0-9a-f]{40}
Author: .+
Date:   .+
""", log))

    def testDetachedRepo(self):
        repotest = os.path.join(self.gitDir, 'repo-test')
        repotestclone = os.path.join(self.gitDir, 'repo-test-clone')
        shelf = gitshelve.open(repository = repotest)
        text = "Hello, world!\n"
        shelf['foo.txt'] = text

        try:
            shelf.sync()

            gitshelve.git('clone', repotest, repotestclone)

            clonedfoo = os.path.join(repotestclone, 'foo.txt')

            try:
                self.assertTrue(os.path.isfile(clonedfoo))

                data = open(clonedfoo)
                try:
                    self.assertEqual(text, data.read())
                finally:
                    data.close()
            finally:
                if os.path.isdir(repotestclone):
                    shutil.rmtree(repotestclone)
        finally:
            del shelf
            if os.path.isdir(repotest):
                shutil.rmtree(repotest)

    def testBlobStore(self):
        blobpath = None
        """Test use a gitshelve as a generic blob store."""
        try:
            blobpath = os.path.join(self.gitDir, 'blobs')
            shelf = gitshelve.open(repository = blobpath, keep_history = False)
            text = "This is just some sample text.\n"
            hash = shelf.put(text)

            buf = StringIO()
            shelf.dump_objects(buf)
            self.assertEqual("""tree: ac
  blob acd291ce81136338a729a30569da2034d918e057: d291ce81136338a729a30569da2034d918e057
""", buf.getvalue())

            self.assertEqual(text, shelf.get(hash))

            shelf.sync()
            buf = StringIO()
            shelf.dump_objects(buf)
            self.assertEqual("""tree 127093ef9a92ebb1f49caa5ecee9ff7139db3a6c
  tree 6c6167149ccc5bf60892b65b84322c1943f5f7da: ac
    blob acd291ce81136338a729a30569da2034d918e057: d291ce81136338a729a30569da2034d918e057
""", buf.getvalue())
            del shelf

            shelf = gitshelve.open(repository = blobpath, keep_history = False)
            buf = StringIO()
            shelf.dump_objects(buf)
            self.assertEqual("""tree 6c6167149ccc5bf60892b65b84322c1943f5f7da: ac
  blob acd291ce81136338a729a30569da2034d918e057: d291ce81136338a729a30569da2034d918e057
""", buf.getvalue())

            self.assertEqual(text, shelf.get(hash))
            del shelf
        finally:
            if blobpath and os.path.isdir(blobpath):
                shutil.rmtree(blobpath)


class NoStdStreams(object):
    def __init__(self,stdout = None, stderr = None):
        self.devnull = open(os.devnull,'w')
        self._stdout = stdout or self.devnull or sys.stdout
        self._stderr = stderr or self.devnull or sys.stderr

    def __enter__(self):
        self.old_stdout, self.old_stderr = sys.stdout, sys.stderr
        self.old_stdout.flush()
        self.old_stderr.flush()
        sys.stdout, sys.stderr = self._stdout, self._stderr

    def __exit__(self, exc_type, exc_value, traceback):
        self._stdout.flush()
        self._stderr.flush()
        sys.stdout = self.old_stdout
        sys.stderr = self.old_stderr
        self.devnull.close()

if __name__ == '__main__':
    unittest.main()
