import pytest

import dlisio

@pytest.fixture(scope="module")
def fpath(tmpdir_factory, merge_files):
    path = str(tmpdir_factory.mktemp('load').join('manylogfiles.dlis'))
    content = [
        'data/semantic/envelope.dlis.part',
        # First logical file, does not have FILE-HEADER
        'data/semantic/origin.dlis.part',
        'data/semantic/channel.dlis.part',
        'data/semantic/frame.dlis.part',
        # Second logical file
        'data/semantic/file-header.dlis.part',
        'data/semantic/origin2.dlis.part',
        'data/semantic/channel-reprcode.dlis.part',
        'data/semantic/frame-reprcode.dlis.part',
        'data/semantic/fdata-reprcode.dlis.part',
        'data/semantic/frame.dlis.part',
        'data/semantic/fdata-reprcode.dlis.part',
        # Third logical file, only has a FILE-HEADER
        'data/semantic/file-header2.dlis.part',
    ]
    merge_files(path, content)
    return path

def test_context_manager(fpath):
    f, *_ = dlisio.load(fpath)
    _ = f.fileheader
    f.close()

    files = dlisio.load(fpath)
    for f in files:
        _ = f.fileheader
        f.close()

    f, *files = dlisio.load(fpath)
    _ = f.fileheader
    for g in files:
        _ = g.fileheader
        g.close()

def test_context_manager_with(fpath):
    with dlisio.load(fpath) as (f, *_):
        _ = f.fileheader

    with dlisio.load(fpath) as files:
        for f in files:
            _ = f.fileheader

    with dlisio.load(fpath) as (f, *files):
        _ = f.fileheader
        for g in files:
            _ = g.fileheader

def test_partitioning(fpath):
    with dlisio.load(fpath) as (f1, f2, f3, *tail):
        assert len(tail) == 0

        assert len(f1.objects) == 8
        assert len(f2.objects) == 32
        assert len(f3.objects) == 1

        key = dlisio.core.fingerprint('FRAME', 'FRAME-REPRCODE', 10, 0)

        assert f1.explicit_indices == [0, 1, 2]
        assert not f1.fdata_index

        assert f2.explicit_indices == [0, 1, 2, 3, 5]
        assert f2.fdata_index[key] == [4, 6]

        assert f3.explicit_indices == [0]
        assert not f3.fdata_index

def test_objects(fpath):
    with dlisio.load(fpath) as (f1, f2, f3):
        fh2 = f2.object('FILE-HEADER', 'N', 10, 0)
        fh3 = f3.object('FILE-HEADER', 'N', 11, 0)

        assert len(f1.fileheader) == 0
        assert len(f1.origin)     == 2
        assert len(f1.channels)   == 4
        assert len(f1.frames)     == 2

        assert fh2.sequencenr == '8'
        assert fh2.id         == 'some logical file'
        assert fh2 not in f3.fileheader

        assert len(f2.origin)   == 1
        assert len(f2.channels) == 27
        assert len(f2.frames)   == 3

        assert fh3.sequencenr == '10'
        assert fh3.id         == 'Yet another logical file'
        assert fh3 not in f2.fileheader

def test_objects_with_encrypted_records(tmpdir_factory, merge_files):
    fpath = str(tmpdir_factory.mktemp('load').join('same-object.dlis'))
    content = [
        'data/semantic/envelope.dlis.part',
        # First logical file
        'data/semantic/file-header.dlis.part',
        'data/semantic/origin.dlis.part',
        'data/semantic/channel.dlis.part',
        'data/semantic/axis-encrypted.dlis.part',
        # Second logical file
        'data/semantic/file-header2.dlis.part',
        'data/semantic/origin2.dlis.part',
        'data/semantic/axis-encrypted.dlis.part',
        'data/semantic/channel-same-objects.dlis.part',
    ]
    merge_files(fpath, content)

    with dlisio.load(fpath) as (f1, f2):
        f1_channel = f1.object('CHANNEL', 'CHANN1', 10, 0)
        f2_channel = f2.object('CHANNEL', 'CHANN1', 10, 0)

        assert len(f1_channel.dimension) == 3
        assert len(f2_channel.dimension) == 1

def test_link(fpath):
    with dlisio.load(fpath) as (f1, f2, _):
        frame1  = f1.object('FRAME', 'FRAME1', 10, 0)
        frame2  = f2.object('FRAME', 'FRAME1', 10, 0)
        channel = f1.object('CHANNEL', 'CHANN1', 10, 0)

        # The same frame is present in two different logical files. The
        # channels in frame.channel are only present in the first
        # logical file. Thus links are not available in the second file.
        assert channel in frame1.channels
        assert channel not in frame2.channels

def test_curves(fpath):
    with dlisio.load(fpath) as (_, f2, _):
        frame = f2.object('FRAME', 'FRAME-REPRCODE', 10, 0)
        curves = frame.curves()

        # Read the first value of the first frame of channel CH01
        assert curves['CH01'][0][0] == 153.0
        assert curves[0]['CH01'][0] == 153.0

        # Read the first value of the second frame of channel CH01
        assert curves['CH01'][1][0] == 153.0
        assert curves[1]['CH01'][0] == 153.0

def test_wellref_coordinates():
    wellref = dlisio.plumbing.wellref.Wellref()
    wellref.attic = {
        'COORDINATE-2-VALUE' : [2],
        'COORDINATE-1-NAME'  : ['longitude'],
        'COORDINATE-3-NAME'  : ['elevation'],
        'COORDINATE-1-VALUE' : [1],
        'COORDINATE-3-VALUE' : [3],
        'COORDINATE-2-NAME'  : ['latitude'],
    }

    wellref.load()

    assert wellref.coordinates['longitude']  == 1
    assert wellref.coordinates['latitude']   == 2
    assert wellref.coordinates['elevation']  == 3

    del wellref.attic['COORDINATE-3-VALUE']
    wellref.load()
    assert wellref.coordinates['latitude']   == 2
    assert wellref.coordinates['elevation']  == None

    del wellref.attic['COORDINATE-2-NAME']
    wellref.load()
    assert wellref.coordinates['longitude']    == 1
    assert wellref.coordinates['COORDINATE-2'] == 2

    del wellref.attic['COORDINATE-1-NAME']
    del wellref.attic['COORDINATE-1-VALUE']
    wellref.load()
    assert len(wellref.coordinates) == 3
    assert wellref.coordinates['COORDINATE-1'] == None

def test_valuetype_mismatch(assert_log):
    tool = dlisio.plumbing.tool.Tool()
    tool.attic = {
        'DESCRIPTION' : ["Description", "Unexpected description"],
        'STATUS'      : ["Yes", 0],
    }
    tool.load()

    assert tool.description == "Description"
    assert tool.status      == True
    assert_log("1 value in the attribute DESCRIPTION")
    assert_log("1 value in the attribute STATUS")
