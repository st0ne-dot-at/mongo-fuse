# Standard modules:
import unittest
import stat

# Third-party modules:
import pymongo
import mongofuse

TEST_DB = "localhost:27017"


class RepresentDatabasesAsFoldersTest(unittest.TestCase):

    def setUp(self):
        self.conn = pymongo.Connection(TEST_DB, safe=True)
        self.fuse = mongofuse.MongoFuse(conn_string=TEST_DB)

    def test_readdir(self):

        # Given number of MongoDB databases
        db1 = self.conn['test_1']
        db2 = self.conn['test_2']
        db3 = self.conn['test_3']

        self.addCleanup(self.conn.drop_database, 'test_1')
        self.addCleanup(self.conn.drop_database, 'test_2')
        self.addCleanup(self.conn.drop_database, 'test_3')

        db1.test.insert({"db": "test_1"})
        db2.test.insert({"db": "test_2"})
        db3.test.insert({"db": "test_3"})

        # When listing files in root dir
        readdir = self.fuse.readdir('/', fh=None)

        # Then database names should appear in listed files
        self.assertIn('test_1', readdir)
        self.assertIn('test_2', readdir)
        self.assertIn('test_3', readdir)

        # And special "." and ".." folders should be listed as well
        self.assertIn(".", readdir)
        self.assertIn("..", readdir)

    def test_getattr(self):

        # Given a MongoDB database
        db = self.conn['test_1']
        db.test.insert({'db': "test_1"})
        self.addCleanup(self.conn.drop_database, 'test_1')

        # When getting attributes for the database folder entry
        attrs = self.fuse.getattr('/test_1')

        # Then folder flag should be set
        self.assertTrue(stat.S_ISDIR(attrs['st_mode']))


class RepresentCollectionsAsSubfoldersTest(unittest.TestCase):

    def setUp(self):
        self.conn = pymongo.Connection(TEST_DB, safe=True)
        self.fuse = mongofuse.MongoFuse(conn_string=TEST_DB)

    def test_readdir(self):

        # Given MongoDB collections
        db_1 = self.conn['test_db_1']
        db_1['collection.1.1'].insert({"foo": "bar"})
        db_1['collection.1.2'].insert({"foo": "bar"})

        db_2 = self.conn['test_db_2']
        db_2['collection.2.1'].insert({"foo": "bar"})
        db_2['collection.2.2'].insert({"foo": "bar"})

        self.addCleanup(self.conn.drop_database, "test_db_1")
        self.addCleanup(self.conn.drop_database, "test_db_2")

        # When listing files in database dir 

        readdir = self.fuse.readdir("/test_db_1",fh=None)
        self.assertIn("collection.1.1", readdir)
        self.assertIn("collection.1.2", readdir)

        readdir = self.fuse.readdir("/test_db_2", fh=None)
        self.assertIn("collection.2.1", readdir)
        self.assertIn("collection.2.2", readdir)

        # And special "." and ".." folders should be listed as well
        self.assertIn(".", readdir)
        self.assertIn("..", readdir)

    def test_getattr(self):

        # Given a MongoDB database
        db_1 = self.conn['test_db_1']
        db_1['collection.1.1'].insert({"foo": "bar"})
        self.addCleanup(self.conn.drop_database, 'test_db_1')

        # When getting attributes for the database folder entry
        attrs = self.fuse.getattr('/test_db_1/collection.1.1')

        # Then folder flag should be set
        self.assertTrue(stat.S_ISDIR(attrs['st_mode']))


class ShowFirstDocumentsAsJsonFilesTest(unittest.TestCase):

    def setUp(self):
        self.conn = pymongo.Connection(TEST_DB, safe=True)
        self.fuse = mongofuse.MongoFuse(conn_string=TEST_DB)

    def test_readdir(self):

        # Given documents in MongoDB collection
        coll = self.conn.test_db.test_collection
        self.addCleanup(self.conn.drop_database, "test_db")
        coll.drop()

        oid_1 = coll.save({"name": "Aleksey", "age": 27})
        oid_2 = coll.save({"name": "Svetlana", "age": 25})

        # When reading contents of the collection dir
        readdir = self.fuse.readdir("/test_db/test_collection", fh=None)

        # Then document's ObjectIDs should be returned as filenames
        self.assertIn("{}.json".format(oid_1), readdir)
        self.assertIn("{}.json".format(oid_2), readdir)

    def test_getattr(self):

        # Given documents in MongoDB collection
        coll = self.conn.test_db.test_collection
        self.addCleanup(self.conn.drop_database, "test_db")
        coll.drop()

        oid_1 = coll.save({"name": "Aleksey", "age": 27})
        oid_2 = coll.save({"name": "Svetlana", "age": 25})

        # When getting attributes for file representing documents
        filename = '/test_db/test_collection/{}.json'.format(oid_1)
        attrs = self.fuse.getattr(filename)

        # Then "regular file" flag should be set
        self.assertTrue(stat.S_ISREG(attrs['st_mode']))
        self.assertFalse(stat.S_ISDIR(attrs['st_mode']))


class SplitPathTest(unittest.TestCase):

    def test_should_split_path_into_list_of_components(self):

        # Given a path
        path = "/tmp/test/my_file.json"

        # When applying split_path() to it
        components = mongofuse.split_path(path)

        # Then list of individual components should be returned
        self.assertEqual(components, ["/", "tmp", "test", "my_file.json"])

    def test_should_normalize_path(self):

        # Given a non-normalized path
        path = "/tmp/test/"

        # When applying split_path() to it
        components = mongofuse.split_path(path)

        # Then list of individual components should be returned
        self.assertEqual(components, ["/", "tmp", "test"])




if __name__ == '__main__':
    unittest.main()
