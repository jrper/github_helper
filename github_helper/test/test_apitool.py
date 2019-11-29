import os
from urllib import error

from pytest import fixture, mark

from github_helper import apitool

@fixture(scope="module")
def api():
    return apitool.GithubAPI(token=os.environ['GISTTOKEN'])

@fixture(scope="module")
def state():
    return {"id":None}

def test_GithubAPI_get_call(api):
    data = api("/repos/octocat/Hello-World")
    print(data)
    assert data["full_name"] == "octocat/Hello-World"


def test_GithubAPI_post_call(api, state):
    data = api("/gists",
               description="A gist created by the github helper app",
               files = { "hello.txt": { "content":"Hello World!\n"}})
    assert len(data["files"]) == 1
    state['id'] = data['id']

def test_GithubAPI_delete_call(api, state):
    if not state['id']:
        test_GithubAPI_post_call(api, state)
    data = api(f"/gists/{state['id']}",
               http_method='DELETE')
    assert data is None

    try:
        data = api(f"/gists/{state['id']}")
        assert False
    except error.HTTPError as err:
        if err.code != 404:
            raise err
    
    
