import json

from github_helper import config


def test_configurator(tmpdir):
    path = tmpdir.join("test.json")
    
    test = config.Configurator(path, {"name":"test"})

    assert test['name'] == "test"

    test['name'] = "test2"

    assert test['name'] == "test2"

    try:

        test['invalid_key']
        assert False
    except KeyError:
        pass


    test._save()

    del test

    test2 = config.Configurator(path, {"name":"test"})

    assert test2['name'] == "test2"
