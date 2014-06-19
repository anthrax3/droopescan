from cement.utils import test
from common.testutils import decallmethods, xml_validate
from lxml import etree
from mock import patch, MagicMock
from plugins.drupal import Drupal
from requests.exceptions import ConnectionError
from tests import BaseTest
import hashlib
import requests
import responses

@decallmethods(responses.activate)
class FingerprintTests(BaseTest):
    """
        Tests related to version fingerprinting for all plugins.
    """

    versions_xsd = "common/versions.xsd"
    xml_file = "tests/versions.xml"

    class MockHash():
        files = None
        def mock_func(self, *args, **kwargs):
            url = kwargs['file_url']
            return self.files[url]

    def setUp(self):
        super(FingerprintTests, self).setUp()
        self.add_argv(["drupal"])
        self.add_argv(["--method", "forbidden"])
        self.add_argv(self.param_version)
        self.scanner = Drupal()

    def mock_xml(self, xml_file, version_to_mock):
        """
            generates all mock data, and patches Drupal.get_hash
        """
        with open(xml_file) as f:
            doc = etree.fromstring(f.read())
            files_xml = doc.xpath("//cms/files/file")

            files = {}
            for file in files_xml:
                url = file.get("url")
                versions = file.xpath("version")
                for file_version in versions:
                    version_number = file_version.get("nb")
                    md5 = file_version.get("md5")

                    if version_number == version_to_mock:
                        files[url] = md5

        mock_hash = self.MockHash()
        mock_hash.files = files
        mock = MagicMock(side_effect=mock_hash.mock_func)

        return mock

    @patch('common.VersionsFile.files_get', return_value=['misc/drupal.js'])
    def test_calls_version(self, m):
        self.respond_several(self.base_url + "%s", {200: ["misc/drupal.js",
            self.scanner.changelog]})
        # with no mocked calls, any HTTP req will cause a ConnectionError.
        self.app.run()

    @test.raises(ConnectionError)
    def test_calls_version_no_mock(self):
        # with no mocked calls, any HTTP req will cause a ConnectionError.
        self.app.run()

    @patch('common.warn')
    @patch('common.VersionsFile.files_get', return_value=['misc/drupal.js'])
    def test_fingerprint_warns_if_changelog(self, m, warn):
        self.respond_several(self.base_url + "%s", {200: ["misc/drupal.js",
            self.scanner.changelog]})

        self.app.run()

        assert warn.called, "should have warned about changelog being present."

    def test_xml_validates_drupal(self):
        drupal = Drupal()

        xml_validate(drupal.versions_file, self.versions_xsd)

    def test_determines_version(self):
        # mock the URLs needed
        real_version = "7.26"
        self.scanner.enumerate_file_hash = self.mock_xml(self.xml_file, real_version)

        version, is_empty = self.scanner.enumerate_version(self.base_url, self.xml_file)

        assert version[0] == real_version
        assert is_empty == False

    def test_enumerate_hash(self):
        file_url = "/misc/drupal.js"
        body = "zjyzjy2076"
        responses.add(responses.HEAD, self.base_url + file_url, body=body)

        actual_md5 = hashlib.md5(body).hexdigest()

        md5 = self.scanner.enumerate_file_hash(requests.head, self.base_url, file_url)

        assert md5 == actual_md5

    @patch('common.VersionsFile.files_get', return_value=['misc/drupal.js'])
    def test_fingerprint_respects_verb(self, patch):
        self.respond_several(self.base_url + "%s", {200: ["misc/drupal.js",
            self.scanner.changelog]}, verb=responses.GET)

        # will exception if attempts to HEAD
        self.scanner.enumerate_version(self.base_url,
                self.scanner.versions_file, self.scanner.changelog, verb='get')

