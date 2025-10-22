from orchestrator.data.features import ema, rsi, bollinger, atr14

def test_ema_len():
    s = [1,2,3,4,5]
    e = ema(s, 3)
    assert len(e) == len(s)

def test_rsi_basic():
    s = [1,2,3,4,5,6,7]
    r = rsi(s, 2)
    assert len(r) == len(s)

def test_bb_shapes():
    s = [i for i in range(1, 60)]
    mid, up, low, bw = bollinger(s, 20, 2.0)
    assert len(mid) == len(up) == len(low) == len(bw) == len(s)

def test_atr14_len():
    from orchestrator.utils.types import Bar
    bars = [Bar(ts=i, open=1, high=2, low=0.5, close=1.5, volume=10) for i in range(30)]
    a = atr14(bars)
    assert len(a) == len(bars)
