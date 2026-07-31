from pipeline.load.common import in_chuncheon_bounds


def test_chuncheon_intake_range_excludes_goseong_coordinate():
    assert in_chuncheon_bounds(127.73, 37.88)
    assert not in_chuncheon_bounds(128.309396140987, 34.9811566456316)
