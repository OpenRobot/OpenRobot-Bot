import re


GIST_REGEX = re.compile(
    r"https?:(www\.)?\/\/gist\.github\.com\/(?P<author>.+)\/(?P<gist_id>[a-zA-Z0-9]+)(#file-(?P<file_name>.+))?"
)

GITHUB_REGEX = re.compile(
    r"https?:(www\.)?\/\/github\.com\/(?P<author>[a-zA-Z0-9\d](?:[a-zA-Z0-9\d]|-(?=[a-zA-Z0-9\d])){0,38})\/(?P<repo>[A-Za-z0-9_.-]+)"
)

HASTEBIN_REGEX = re.compile(
    r"https?:\/\/(www\.)?(toptal.com\/developers\/hastebin|hastebin.com)\/(?P<key>.+)"
)