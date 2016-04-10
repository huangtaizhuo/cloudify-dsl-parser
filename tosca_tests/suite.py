# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
from uuid import uuid4
from shutil import rmtree
from functools import wraps, partial
from itertools import imap
from tempfile import mkdtemp
from testtools import TestCase
from multiprocessing import Process

from tosca_parser import Parser


class TimeoutTestMixin(TestCase):
    def timeout_decorator(self, func=None, seconds=10):
        if not func:
            return partial(self.timeout_decorator, seconds=seconds)

        @wraps(func)
        def wrapper(*args, **kwargs):
            process = Process(target=func, args=args, kwargs=kwargs)
            process.start()
            process.join(seconds)
            if process.exitcode != 0:
                process.terminate()
                self.fail(
                    'timeout decorator timedout, process exitcode: {0}'
                        .format(process.exitcode))

        return wrapper
    timeout_decorator = staticmethod(timeout_decorator)


class TempDirectoryTestCase(TestCase):
    def __init__(self, *args, **kwargs):
        super(TempDirectoryTestCase, self).__init__(*args, **kwargs)
        self.temp_directory = None
        self._path_to_uri = 'file://{0}'.format

    def setUp(self):
        self.temp_directory = mkdtemp(prefix=self.__class__.__name__)
        super(TempDirectoryTestCase, self).setUp()

    def tearDown(self):
        rmtree(self.temp_directory, ignore_errors=True)
        super(TempDirectoryTestCase, self).tearDown()

    def write_to_file(self, content, filename, directory=None):
        directory = os.path.join(self.temp_directory, directory or '')
        if not os.path.exists(directory):
            os.makedirs(directory)

        file_path = os.path.join(directory, filename)
        with open(file_path, 'w') as file_obj:
            file_obj.write(content)
        return file_path

    def make_yaml_file(self, content, as_uri=False):
        filename = 'tempfile{0}.yaml'.format(uuid4())
        path = self.write_to_file(content, filename)
        return path if not as_uri else self._path_to_uri(path)

    def create_yaml_with_imports(self, contents, as_uri=False):
        import_path_maker = (
            (lambda path: path)
            if as_uri else
            self._path_to_uri)

        def import_creator(content):
            path = self.make_yaml_file(content)
            return import_path_maker(path)

        return '\nimports:{0}'.format(
            '\n    -   '.join(imap(import_creator, contents)))


class ParserTestCase(TestCase):
    def __init__(self, *args, **kwargs):
        super(ParserTestCase, self).__init__(*args, **kwargs)
        self.template = None

    def setUp(self):
        self.template = Template()
        super(ParserTestCase, self).setUp()

    def tearDown(self):
        self.template = None
        super(ParserTestCase, self).tearDown()

    def parse(self, import_resolver=None, validate_version=True):
        parser = Parser(import_resolver=import_resolver,
                        validate_version=validate_version)
        return parser.parse_from_string(str(self.template))

    def assert_parser_raise_exception(
            self, error_code, exception_types, extra_tests=()):
        try:
            self.parse()
            self.fail()
        except exception_types as exc:
            self.assertEquals(error_code, exc.err_code)
            for test in extra_tests:
                test(exc)
        return exc


class Template(object):
    def __init__(self):
        self.template = ''

    def __str__(self):
        return self.template

    def __iadd__(self, other):
        self.template += other
        return self

    def version_section(self, version):
        self.template += ('\ntosca_definitions_version: cloudify_dsl_{0}\n'
                          .format(version.replace('.', '_')))

    def node_type_section(self, **kwargs):
        self.template += (
            '\nnode_types:\n'
            '    test_type:\n'
            '        properties:\n'
            '            key:\n'
            '                default: "default"\n'
        )

    def node_template_section(self):
        self.template += (
            '\nnode_templates:\n'
            '    test_node:\n'
            '        type: test_type\n'
            '        properties:\n'
            '            key: "val"\n'
        )

    def data_types_section(
            self,
            properties_first='{}',
            properties_second='{}',
            extras=''):
        self.template += (
            '\ndata_types:\n'
            '    pair_type:\n'
            '        properties:\n'
            '            first: {properties_first}\n'
            '            second: {properties_second}\n'
            '{extras}\n'
            .format(properties_first=properties_first,
                    properties_second=properties_second,
                    extras=extras)
        )


def get_node_by_name(plan, name):
        return [x for x in plan.node_templates if x['name'] == name][0]
