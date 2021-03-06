# Standard modules:
import unittest
import stat
import textwrap
import datetime
import time

# Third-party modules:
import pymongo
import bson
import mongofuse
import fuse

TEST_DB = "localhost:27017"


class FuseTest(unittest.TestCase):

    def setUp(self):
        self.conn = pymongo.Connection(TEST_DB, safe=True)
        self.fuse = mongofuse.MongoFuse(conn_string=TEST_DB)
        self.fuse.attrs_cache = mongofuse.LRUCache(expire_secs=0)

        self.conn.drop_database('test_db')
        self.addCleanup(self.conn.drop_database, 'test_db')


class RepresentDatabasesAsFoldersTest(FuseTest):

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
    
    def test_getattr_cache(self):

        # Given attributes caching is on
        self.fuse.attrs_cache = mongofuse.LRUCache(expire_secs=100)

        # And MongoDB database exists
        db = self.conn.test_db.create_collection('dummy')

        # When calling readdir
        self.fuse.readdir('/')

        # Then database attributes should be cached
        # We use a side-effect of caching here: database would be still
        # visible by getattr after actualy deleting it
        self.conn.drop_database('test_db')
        attrs = self.fuse.getattr('/test_db')
        self.assertTrue(stat.S_ISDIR(attrs['st_mode']))


class RepresentCollectionsAsSubfoldersTest(FuseTest):

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
    
    def test_getattr_cache(self):

        # Given attributes caching is on
        self.fuse.attrs_cache = mongofuse.LRUCache(expire_secs=100)

        # And MongoDB collection exists
        db = self.conn.test_db.test_coll.insert({"foo": "bar"})

        # When calling readdir
        self.fuse.readdir('/test_db')

        # Then attributes for collections should be cached
        # We use a side-effect of caching here: entries are still
        # visible by getattr after actualy deleting it
        self.conn.drop_database('test_db')
        attrs = self.fuse.getattr('/test_db/test_coll')
        self.assertTrue(stat.S_ISDIR(attrs['st_mode']))


class ShowFirstDocumentsAsJsonFilesTest(FuseTest):

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

    def test_getattr_cache(self):

        # Given attributes caching is on
        self.fuse.attrs_cache = mongofuse.LRUCache(expire_secs=100)

        # And db documents
        coll = self.conn.test_db.test_collection
        oid_1 = coll.save({"name": "Aleksey", "age": 27})

        # When calling readdir
        self.fuse.readdir('/test_db/test_collection')

        # Then file attributes should be cached for a while
        # We use side-effect of caching here: document would be still
        # visible by getattr after actualy deleting it
        coll.remove(oid_1)
        fname = '/test_db/test_collection/{}.json'.format(oid_1)
        attrs = self.fuse.getattr(fname)
        self.assertTrue(attrs['st_size'])
        self.assertTrue(stat.S_ISREG(attrs['st_mode']))

    def test_read_whole_file(self):

        # Given MongoDB document
        coll = self.conn.test_db.test_collection
        oid = coll.save({"name": "Aleksey", "age": 27})

        # When reading a file representing the document
        filename = '/test_db/test_collection/{}.json'.format(oid)
        content = self.fuse.read(filename, 1000, 0, fh=None)

        # Then pretty-printed JSON should be returned
        self.assertMultiLineEqual(content, textwrap.dedent("""\
                {
                    "_id": {
                        "$oid": "%s"
                    }, 
                    "age": 27, 
                    "name": "Aleksey"
                }""" % oid))

    def test_read_random_block(self):

        # Given MongoDB document
        coll = self.conn.test_db.test_collection
        oid = coll.save({"name": "Aleksey", "age": 27})

        # When reading blocks of random size at arbitrary positions from the
        # file representing the document
        filename = '/test_db/test_collection/{}.json'.format(oid)
        block_1 = self.fuse.read(filename, size=6, offset=5, fh=None)
        block_2 = self.fuse.read(filename, size=1, offset=1, fh=None)
        block_3 = self.fuse.read(filename, size=1000, offset=1000, fh=None)

        # Then corresponding parts of content should be returned
        self.assertEqual(block_1, ' "_id"')
        self.assertEqual(block_2, "\n")
        self.assertEqual(block_3, "")

    def test_raise_error_on_unexisting_files(self):

        # Error should be raised when attempting to access file that doesn't
        # represent existing doc and has no special meaning,
        with self.assertRaises(fuse.FuseOSError):
            self.fuse.read("/test_db/test_coll/some_file.txt", size=1000)

        with self.assertRaises(fuse.FuseOSError):
            self.fuse.getattr("/test_db/test_coll/some_file.txt")

    def test_find_doc(self):

        # Given MongoDB document
        coll = self.conn.test_db.test_coll
        self.addCleanup(self.conn.drop_database, "test_db")
        coll.drop()

        oid = coll.save({"name": "Svetlana", "age": 25})

        # When finding document by path
        doc = self.fuse._find_doc("/test_db/test_coll/{}.json".format(oid))

        # Then Mongo document should be returned
        self.assertIsNotNone(doc)
        self.assertEqual(doc['_id'], oid)
        self.assertEqual(doc['name'], "Svetlana")
        self.assertEqual(doc['age'], 25)


class FilterCollectionsWithSavedQueries(FuseTest):

    def test_should_return_only_matching_documents_when_query_file_present(self):

        # Given query file in collection subfolder
        query = '{"age": {"$lte": 25}}'
        self.fuse.write("/test_db/test_coll/query.json",
                        query,
                        offset=0,
                        fh=None)

        # And mongodb documents
        coll = self.conn.test_db.test_coll
        coll.drop()
        oid_1 = coll.save({"name": "Svetlana", "age": 25})
        oid_2 = coll.save({"name": "Juliana", "age": 0})
        oid_3 = coll.save({"name": "Aleksey", "age": 27})

        # When listing files in dir
        readdir = self.fuse.readdir("/test_db/test_coll", fh=None)

        # Then only matching docs should be listed
        self.assertIn("{}.json".format(oid_1), readdir)
        self.assertIn("{}.json".format(oid_2), readdir)
        self.assertNotIn("{}.json".format(oid_3), readdir)

    def test_should_read_saved_query_files(self):

        # When saving query.json file
        query = '{"foo": "bar"}'
        filename = "/test_db/test_coll/query.json"
        self.fuse.write(filename, query)

        # Then it should be listed by readdir
        self.assertIn("query.json", self.fuse.readdir("/test_db/test_coll"))

        # And its content should be returned by read
        content = self.fuse.read(filename, 1000)
        self.assertEqual(query, content)

        # And length should be reported by getattr
        self.assertEqual(self.fuse.getattr(filename)['st_size'], len(query))

    def test_should_treat_subfolder_name_as_placeholder_substitution(self):

        # Given query.json file with a parameter placeholder
        query = '{"foo": "$1"}'
        filename = "/test_db/test_coll/query.json"
        self.fuse.write(filename, query)

        # When subfolder exists for this path
        self.fuse.mkdir("/test_db/test_coll/bar", 0777)

        # Then query's placeholder should be substituted for the folder name
        query = self.fuse._get_query('/test_db/test_coll/bar')
        self.assertEqual(query, {"foo": "bar"})


class CreateDocumentTest(FuseTest):

    def test_should_create_new_doc_when_writing_special_file(self):

        self.conn.drop_database("test_db")

        # When writing to special "new.json" file
        content = '{"foo": "bar"}'
        self.fuse.write("/test_db/test_coll/new.json", content)

        # Then new document should be created in database
        doc = self.conn.test_db.test_coll.find_one()
        self.assertIsNotNone(doc)
        self.assertEqual(doc['foo'], "bar")

    def test_should_create_new_doc_when_filename_looks_like_objectid(self):

        # When writing to a file with objectid-like name
        content = '{"foo": "bar"}'
        oid = bson.objectid.ObjectId()
        filename = "/test_db/test_coll/{}.json".format(oid)
        self.fuse.create(filename, 0755)
        self.fuse.write(filename, content)

        # Then MongoDB document with this id should be created
        doc = self.conn['test_db']['test_coll'].find_one(oid)
        self.assertIsNotNone(doc)
        self.assertEqual(doc['foo'], 'bar')


class EditExistingDocsTest(FuseTest):

    def test_should_update_existing_documents_on_file_write(self):

        # Given MongoDB document
        coll = self.conn.test_db.test_coll
        oid = coll.save({"foo": "bar"})

        # When writing to the file which represents this document
        filename = "/test_db/test_coll/{}.json".format(oid)
        new_doc = '''{"_id": {"$oid": "%s"},
                      "foo": "bar2",
                      "new": "key"}
                  ''' % oid
        self.fuse.write(filename, new_doc, 0)

        # Then document in MongoDB should be updated
        doc = coll.find_one(bson.objectid.ObjectId(oid))
        self.assertEqual(doc['foo'], 'bar2')
        self.assertEqual(doc['new'], 'key')


class DeleteDocumentTest(FuseTest):

    def test_should_delete_mongo_doc_on_unlink_file_operation(self):

        # Given MongoDB document
        coll = self.conn.test_db.test_coll
        oid = coll.save({"foo": "bar"})

        # When deleting corresponding file
        filename = "/test_db/test_coll/{}.json".format(oid)
        self.fuse.unlink(filename)

        # Then document should be removed from database
        doc = coll.find_one(bson.objectid.ObjectId(oid))
        self.assertIsNone(doc)


class CreateDatabaseAndCollectionTest(FuseTest):

    def test_should_create_new_db_and_collection_with_mkdir(self):

        # Given absent test database
        self.conn.drop_database("test_db")

        # When creating folder
        self.fuse.mkdir("/test_db", 0755)
        self.fuse.mkdir("/test_db/test_coll", 0755)

        # Then new database and/or collection should be created
        self.assertIn('test_db', self.conn.database_names())
        self.assertIn('test_coll', self.conn.test_db.collection_names())


class CreateCustomCollectionViews(FuseTest):

    def test_should_create_subfolder_in_collection_folders(self):

        # Given MongoDB database and collection
        self.conn.test_db.create_collection('test_coll')

        # When creating subfolder under collection dir
        self.fuse.mkdir("/test_db/test_coll/subfolder", 0755)

        # Then it should be listed
        readdir = self.fuse.readdir("/test_db/test_coll")
        self.assertIn("subfolder", readdir)

        # And it should be marked with directory flag
        attrs = self.fuse.getattr("/test_db/test_coll")
        self.assertTrue(stat.S_ISDIR(attrs['st_mode']))

    def test_should_generate_query_file_from_special_folder_names(self):

        # Given MongoDB database and collection
        self.conn.test_db.create_collection('test_coll')

        # When creating subfolder with a special name "by_field"
        self.fuse.mkdir("/test_db/test_coll/by_testId", 0777)

        # Then query.json should be generated in this folder
        query = self.fuse.read("/test_db/test_coll/by_testId/query.json", 100)
        self.assertEqual(query, '{"testId": $1}')


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


class DumpsTest(unittest.TestCase):

    def test_should_return_pretty_printed_bson_documents(self):

        # Given a document
        doc = {"age": 26,
               "name": "Svetlana", 
               "skills": [{
                   "skill": "C++",
                   "level": 7
                },
                {
                    "skill": "Python",
                    "level": 7
                }]
            }

        # dumps() should return pretty-printed version of the document
        expected = textwrap.dedent("""\
            {
                "age": 26, 
                "name": "Svetlana", 
                "skills": [
                    {
                        "level": 7, 
                        "skill": "C++"
                    }, 
                    {
                        "level": 7, 
                        "skill": "Python"
                    }
                ]
            }""")
        self.maxDiff = None
        self.assertMultiLineEqual(mongofuse.dumps(doc), expected)

    @unittest.skip("implement human readable datetimes")
    def test_should_encode_datetime_objects(self):

        doc = {"dt": datetime.datetime(2012, 6, 30, 22, 00)}
        expected = textwrap.dedent("""\
                {
                    "dt": ISODate("2012-06-30T22:00:00Z")
                }""")
        self.assertMultiLineEqual(mongofuse.dumps(doc), expected)


class LRUCacheTest(unittest.TestCase):

    def test_should_behave_like_ordinary_dict(self):

        # Given LRU cache with a large expiration time (so we won't reach it)
        cache = mongofuse.LRUCache(expire_secs=100)

        # Then it should behave like ordinary dict:
        cache['answer'] = 42
        self.assertIn('answer', cache)
        self.assertEqual(cache['answer'], 42)
        self.assertEqual(cache.get('dunno', '?'), '?')
        with self.assertRaises(KeyError):
            cache['boom!']

    def test_should_remove_expired_items(self):

        # Given filled cache
        cache = mongofuse.LRUCache(expire_secs=1)
        cache['answer'] = 42

        # When expiration time has been passed
        time.sleep(1.5)

        # Then outdated items should be removed from cache
        self.assertNotIn('answer', cache)


if __name__ == '__main__':
    unittest.main()
